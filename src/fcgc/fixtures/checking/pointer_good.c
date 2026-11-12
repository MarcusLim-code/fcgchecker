#include <stddef.h>
int store(int *out) {
    if (out == NULL) return -1;
    *out = 7;
    return 0;
}
