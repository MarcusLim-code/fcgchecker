#include <stddef.h>
typedef int (*sample_callback)(void *, int);
int on_sample(void *context, int value) {
    *(int *)context = value;
    return 0;
}
int dispatch(sample_callback callback, void *context) {
    if (callback == NULL) return -1;
    callback(context, 7);
    return 0;
}
