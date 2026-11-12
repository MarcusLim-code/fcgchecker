int lock_bus(void);
void unlock_bus(void);
int device_open(void);
void device_close(int handle);
int transact(int handle);
int run_bus(void) {
    if (lock_bus() != 0) return -1;
    int handle = device_open();
    if (handle < 0) { unlock_bus(); return handle; }
    int rc = transact(handle);
    device_close(handle);
    unlock_bus();
    return rc;
}
