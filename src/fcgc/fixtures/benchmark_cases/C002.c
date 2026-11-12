#include <stddef.h>
int sensor_open(void **handle);
int sensor_configure(void *handle);
int boot_sensor(void) {
    void *handle = NULL;
    sensor_open(&handle);
    return sensor_configure(handle);
}
