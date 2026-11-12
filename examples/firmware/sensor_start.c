/* Synthetic introductory example, not production firmware. */
extern int sensor_open(int *handle);
extern int sensor_configure(int handle, unsigned mode);

int start_sensor(unsigned mode)
{
    int handle = -1;
    int status = sensor_open(&handle);
    if (status != 0)
        return status;
    return sensor_configure(handle, mode);
}
