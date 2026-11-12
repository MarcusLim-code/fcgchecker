#include <stddef.h>
int sensor_open(void **handle);
int sensor_configure(void *handle);
int boot_sensor(void) {
    void *handle = NULL;
    int rc = sensor_open(&handle);
    if (rc != 0) return rc;
    return sensor_configure(handle);
}
