# Credential Provisioning (NVS)

Wi-Fi credentials are **never** committed to git (PS-AUDIT-012). The firmware reads its
SSID/password, node id, and aggregator target from the `csi_cfg` NVS namespace at boot
(`main/nvs_config.c`); the `CONFIG_CSI_WIFI_*` values in `sdkconfig.defaults` are
placeholders (`REPLACE_ME`) used only as build-time fallbacks and must stay placeholders.
To provision a board, flash the NVS partition locally at flash time:

```
python esp-flash.py --port COM7 --ssid "YourSSID" --password "YourPassword" --target-ip <aggregator-ip>
```

`esp-flash.py` builds an NVS CSV (`ssid`, `password`, target keys in namespace `csi_cfg`),
generates a partition image with `nvs_partition_gen`, and writes it to the NVS partition at
offset `0x9000`. The generated `nvs_node*.bin` images and your local `sdkconfig`/
`sdkconfig.old` contain real credentials — they are gitignored here and must never be
re-added to version control.
