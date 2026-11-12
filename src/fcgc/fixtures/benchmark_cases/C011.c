#define BUSY 1
#define IO_ERROR 2
#define TIMEOUT 3
int perform(void);
int transaction(int *last_error, unsigned now, unsigned deadline) {
    *last_error = 0;
    int rc = perform();
    for (unsigned tries = 0; rc == BUSY && tries < 2u; ++tries) rc = perform();
    if (rc != 0) { *last_error = rc; return rc; }
    if (now >= deadline) return TIMEOUT;
    return 0;
}
