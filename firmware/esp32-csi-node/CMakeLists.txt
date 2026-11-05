# ESP32 CSI Node Firmware (ADR-018)
# Requires ESP-IDF v5.2+
cmake_minimum_required(VERSION 3.16)

set(EXTRA_COMPONENT_DIRS "")

# version.txt (ADR-018 port) is auto-detected by ESP-IDF's project.cmake and
# fed into esp_app_get_description()->version with no format restriction —
# do not also pass project(... VERSION ...), which requires strict numeric
# semver and would hard-fail idf.py build on a tag like "0.2.0-rc1".

include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(esp32-csi-node)
