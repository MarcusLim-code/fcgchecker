#include <stddef.h>
typedef int (*sample_callback)(void *, int);
int on_sample(void *context, int value) {
    if (context == NULL) return -1;
    *(int *)context = value;
    return 0;
}
int dispatch(sample_callback callback, void *context) {
    if (callback == NULL) return -1;
    int rc = callback(context, 7);
    if (rc != 0) return rc;
    return 0;
}
