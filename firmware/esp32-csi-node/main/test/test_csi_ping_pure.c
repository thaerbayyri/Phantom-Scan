/**
 * @file test_csi_ping_pure.c
 * @brief Host unit tests for csi_ping_pure.h.
 *
 * Build and run on a host with gcc:
 *   gcc -std=c99 -O2 -Wall -I.. test_csi_ping_pure.c -o test_csi_ping_pure
 *   ./test_csi_ping_pure
 */

#include "../csi_ping_pure.h"

#include <stdio.h>
#include <stdlib.h>

#define CHECK(cond)                                                              \
    do {                                                                         \
        if (!(cond)) {                                                           \
            fprintf(stderr, "FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond);      \
            exit(1);                                                             \
        }                                                                        \
    } while (0)

int main(void)
{
    /* A lost reply may cost at most one slot. */
    CHECK(CSI_PING_TIMEOUT_MS < CSI_PING_INTERVAL_MS);
    /* The send gate must be shorter than the ping interval or it aliases. */
    CHECK(CSI_MIN_SEND_INTERVAL_MS < CSI_PING_INTERVAL_MS);

    /* Four consecutive node ids get four distinct offsets inside one interval. */
    uint32_t seen[4];
    for (uint8_t id = 1; id <= 4; id++) {
        uint32_t off = csi_ping_start_offset_ms(id, CSI_PING_INTERVAL_MS);
        CHECK(off < CSI_PING_INTERVAL_MS);
        seen[id - 1] = off;
    }
    for (int i = 0; i < 4; i++) {
        for (int j = i + 1; j < 4; j++) {
            CHECK(seen[i] != seen[j]);
        }
    }

    /* Ids wrap by slot count; a zero interval never yields an offset. */
    CHECK(csi_ping_start_offset_ms(4, 25) == csi_ping_start_offset_ms(0, 25));
    CHECK(csi_ping_start_offset_ms(2, 0) == 0);

    printf("test_csi_ping_pure: all checks passed\n");
    return 0;
}
