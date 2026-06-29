/**
 * @file stream_sender.c
 * @brief UDP stream sender for CSI frames.
 *
 * Opens a UDP socket and sends serialized ADR-018 frames to the aggregator.
 */

#include "stream_sender.h"

#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "lwip/sockets.h"
#include "lwip/netdb.h"
#include "sdkconfig.h"

static const char *TAG = "stream_sender";

static int s_sock = -1;
static struct sockaddr_in s_dest_addr;
static TaskHandle_t s_sender_task_handle = NULL;

/**
 * ENOMEM backoff state.
 * When sendto fails with ENOMEM (errno 12), we suppress further sends for
 * a cooldown period to let lwIP reclaim packet buffers.  Without this,
 * rapid-fire CSI callbacks can exhaust the pbuf pool and crash the device.
 */
static int64_t s_backoff_until_us = 0;       /* esp_timer timestamp to resume */
#define ENOMEM_COOLDOWN_MS  100              /* suppress sends for 100 ms */
#define ENOMEM_LOG_INTERVAL 50               /* log every Nth suppressed send */
static uint32_t s_enomem_suppressed = 0;
#define STREAM_SENDER_MAX_PACKET_SIZE 768
#define STREAM_SENDER_QUEUE_SLOTS 32

typedef struct {
    uint16_t len;
    uint8_t data[STREAM_SENDER_MAX_PACKET_SIZE];
} stream_sender_packet_t;

static QueueHandle_t s_queue_handle = NULL;
static uint32_t s_queue_drops = 0;

static void stream_sender_task(void *arg)
{
    (void)arg;
    stream_sender_packet_t pkt;

    while (1) {
        if (xQueueReceive(s_queue_handle, &pkt, portMAX_DELAY) != pdTRUE) {
            continue;
        }

        while (1) {
            if (s_sock < 0) {
                vTaskDelay(pdMS_TO_TICKS(10));
                continue;
            }

            if (s_backoff_until_us > 0) {
                int64_t now = esp_timer_get_time();
                if (now < s_backoff_until_us) {
                    vTaskDelay(pdMS_TO_TICKS(ENOMEM_COOLDOWN_MS));
                    continue;
                }
                ESP_LOGI(TAG, "ENOMEM backoff expired, resuming sends (%lu were suppressed)",
                         (unsigned long)s_enomem_suppressed);
                s_backoff_until_us = 0;
                s_enomem_suppressed = 0;
            }

            int sent = sendto(s_sock, pkt.data, pkt.len, 0,
                              (struct sockaddr *)&s_dest_addr, sizeof(s_dest_addr));
            if (sent >= 0) {
                vTaskDelay(pdMS_TO_TICKS(1));
                break;
            }

            if (errno == ENOMEM) {
                s_backoff_until_us = esp_timer_get_time() +
                                     (int64_t)ENOMEM_COOLDOWN_MS * 1000;
                s_enomem_suppressed++;
                if ((s_enomem_suppressed % ENOMEM_LOG_INTERVAL) == 1) {
                    ESP_LOGW(TAG, "sendto ENOMEM in sender task - retrying after %d ms",
                             ENOMEM_COOLDOWN_MS);
                }
                vTaskDelay(pdMS_TO_TICKS(ENOMEM_COOLDOWN_MS));
                continue;
            }

            ESP_LOGW(TAG, "sendto failed: errno %d", errno);
            vTaskDelay(pdMS_TO_TICKS(1));
            break;
        }
    }
}

static int sender_init_internal(const char *ip, uint16_t port)
{
    s_sock = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
    if (s_sock < 0) {
        ESP_LOGE(TAG, "Failed to create socket: errno %d", errno);
        return -1;
    }

    memset(&s_dest_addr, 0, sizeof(s_dest_addr));
    s_dest_addr.sin_family = AF_INET;
    s_dest_addr.sin_port = htons(port);

    if (inet_pton(AF_INET, ip, &s_dest_addr.sin_addr) <= 0) {
        ESP_LOGE(TAG, "Invalid target IP: %s", ip);
        close(s_sock);
        s_sock = -1;
        return -1;
    }

    int sndbuf = 16 * 1024;
    setsockopt(s_sock, SOL_SOCKET, SO_SNDBUF, &sndbuf, sizeof(sndbuf));

    if (s_queue_handle == NULL) {
        s_queue_handle = xQueueCreate(STREAM_SENDER_QUEUE_SLOTS, sizeof(stream_sender_packet_t));
        if (s_queue_handle == NULL) {
            ESP_LOGE(TAG, "Failed to create sender queue");
            close(s_sock);
            s_sock = -1;
            return -1;
        }
    }

    if (s_sender_task_handle == NULL) {
        BaseType_t ret = xTaskCreatePinnedToCore(
            stream_sender_task,
            "udp_sender",
            4096,
            NULL,
            2,
            &s_sender_task_handle,
            1
        );
        if (ret != pdPASS) {
            ESP_LOGE(TAG, "Failed to start sender task");
            close(s_sock);
            s_sock = -1;
            return -1;
        }
    }

    ESP_LOGI(TAG, "UDP sender initialized: %s:%d", ip, port);
    return 0;
}

int stream_sender_init(void)
{
    return sender_init_internal(CONFIG_CSI_TARGET_IP, CONFIG_CSI_TARGET_PORT);
}

int stream_sender_init_with(const char *ip, uint16_t port)
{
    return sender_init_internal(ip, port);
}

int stream_sender_send(const uint8_t *data, size_t len)
{
    if (s_sock < 0 || data == NULL || len == 0) {
        return -1;
    }

    if (len > STREAM_SENDER_MAX_PACKET_SIZE) {
        ESP_LOGW(TAG, "packet too large for sender queue: %u", (unsigned)len);
        return -1;
    }

    stream_sender_packet_t pkt;
    pkt.len = (uint16_t)len;
    memcpy(pkt.data, data, len);

    if (xQueueSend(s_queue_handle, &pkt, 0) != pdTRUE) {
        s_queue_drops++;
        if ((s_queue_drops % ENOMEM_LOG_INTERVAL) == 1) {
            ESP_LOGW(TAG, "sender queue full, dropped %lu packets",
                     (unsigned long)s_queue_drops);
        }
        return -1;
    }

    return (int)len;
}

void stream_sender_deinit(void)
{
    if (s_sock >= 0) {
        close(s_sock);
        s_sock = -1;
        ESP_LOGI(TAG, "UDP sender closed");
    }
}
