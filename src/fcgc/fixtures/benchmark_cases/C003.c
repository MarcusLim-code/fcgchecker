#include <stddef.h>
int scale(const int *input, int *output) {
    if (input == NULL || output == NULL) return -1;
    *output = *input * 2;
    return 0;
}
