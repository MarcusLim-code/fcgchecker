#define BUSY 1
#define IO_ERROR 2
#define TIMEOUT 3
int perform(void);
int transaction(int *last_error, unsigned now, unsigned deadline) {
    int rc = perform();
    for (unsigned tries = 0; rc != 0 && tries < 3u; ++tries) rc = perform();
    if (rc == IO_ERROR) { *last_error = rc; return 0; }
    if (now >= deadline) return IO_ERROR;
    return 0;
}
