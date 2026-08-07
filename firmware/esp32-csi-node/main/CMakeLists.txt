set(SRCS
    "main.c" "csi_collector.c" "stream_sender.c" "nvs_config.c"
    "edge_processing.c" "edge_dsp_pure.c" "rv_feature_state.c" "ota_update.c" "power_mgmt.c"
    "wasm_runtime.c" "wasm_upload.c" "rvf_parser.c"
    "display_task.c"
)

set(REQUIRES
    esp_event
    esp_http_server
    esp_netif
    esp_pm
    esp_timer
    esp_wifi
    lwip
    mbedtls
    nvs_flash
)

# ADR-045: AMOLED display support (compile-time optional)
if(CONFIG_DISPLAY_ENABLE)
    list(APPEND SRCS "display_hal.c" "display_ui.c")
    list(APPEND REQUIRES esp_lcd esp_lcd_touch lvgl)
endif()

idf_component_register(
    SRCS ${SRCS}
    INCLUDE_DIRS "."
    PRIV_REQUIRES app_update
    REQUIRES ${REQUIRES}
)
