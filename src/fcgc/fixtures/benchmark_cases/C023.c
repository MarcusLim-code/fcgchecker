#include <stdint.h>
typedef int (*transform_fn)(uint32_t);
int apply_transform(transform_fn operation, uint32_t value) {
    /* The local contract does not define whether the integer is data or status. */
    return operation(value);
}
