/* Synthetic firmware fixture: a memory-mapped sensor with polling and IRQ paths.
 * This is research input, not a hardware driver for a specific device.
 */
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define SENSOR_BASE_ADDRESS ((uintptr_t)0x40012000u)
#define SENSOR_QUEUE_CAPACITY 16u
#define SENSOR_DEFAULT_TIMEOUT 2000u
#define SENSOR_MAX_RAW 4095

#define SENSOR_STATUS_READY (1u << 0)
#define SENSOR_STATUS_OVERRUN (1u << 1)
#define SENSOR_STATUS_FAULT (1u << 2)
#define SENSOR_CONTROL_ENABLE (1u << 0)
#define SENSOR_CONTROL_START (1u << 1)
#define SENSOR_CONTROL_IRQ_ENABLE (1u << 2)

typedef struct {
    volatile uint32_t control;
    volatile uint32_t status;
    volatile uint32_t data;
    volatile uint32_t irq_status;
    volatile uint32_t irq_clear;
    volatile uint32_t prescaler;
} SensorRegisters;

typedef enum {
    SENSOR_IDLE,
    SENSOR_WAITING,
    SENSOR_READY,
    SENSOR_TIMED_OUT,
    SENSOR_FAILED
} SensorState;

typedef enum {
    SENSOR_OK,
    SENSOR_BUSY,
    SENSOR_EMPTY,
    SENSOR_BAD_ARGUMENT,
    SENSOR_HARDWARE_ERROR,
    SENSOR_TIMEOUT
} SensorResult;

typedef struct {
    uint16_t value;
    uint32_t sequence;
    uint32_t tick;
} SensorSample;

typedef struct {
    uint32_t completed;
    uint32_t timeouts;
    uint32_t overruns;
    uint32_t faults;
    uint32_t dropped;
} SensorStats;

typedef struct {
    SensorRegisters *registers;
    volatile SensorState state;
    volatile uint32_t irq_epoch;
    uint32_t sequence;
    uint32_t deadline;
    int16_t offset;
    uint16_t gain_q8;
    SensorSample queue[SENSOR_QUEUE_CAPACITY];
    volatile uint8_t head;
    volatile uint8_t tail;
    SensorStats stats;
} SensorController;

static uint8_t next_index(uint8_t index) {
    return (uint8_t)((index + 1u) % SENSOR_QUEUE_CAPACITY);
}

static bool deadline_passed(uint32_t now, uint32_t deadline) {
    return (int32_t)(now - deadline) >= 0;
}

static uint16_t calibrate(const SensorController *controller, uint16_t raw) {
    int32_t adjusted = ((int32_t)raw * controller->gain_q8) / 256;
    adjusted += controller->offset;
    if (adjusted < 0) {
        return 0u;
    }
    if (adjusted > SENSOR_MAX_RAW) {
        return SENSOR_MAX_RAW;
    }
    return (uint16_t)adjusted;
}

static bool queue_sample(SensorController *controller, uint16_t raw, uint32_t tick) {
    uint8_t next = next_index(controller->head);
    if (next == controller->tail) {
        controller->stats.dropped++;
        return false;
    }
    SensorSample *sample = &controller->queue[controller->head];
    sample->value = calibrate(controller, raw);
    sample->sequence = ++controller->sequence;
    sample->tick = tick;
    controller->head = next;
    controller->stats.completed++;
    return true;
}

void sensor_controller_init(SensorController *controller, uint32_t prescaler) {
    if (controller == NULL) {
        return;
    }
    controller->registers = (SensorRegisters *)SENSOR_BASE_ADDRESS;
    controller->state = SENSOR_IDLE;
    controller->irq_epoch = 0u;
    controller->sequence = 0u;
    controller->deadline = 0u;
    controller->offset = 0;
    controller->gain_q8 = 256u;
    controller->head = 0u;
    controller->tail = 0u;
    controller->stats = (SensorStats){0};
    controller->registers->control = 0u;
    controller->registers->irq_clear = 0xffffffffu;
    controller->registers->prescaler = prescaler;
    controller->registers->control = SENSOR_CONTROL_ENABLE;
}

SensorResult sensor_controller_start(SensorController *controller, uint32_t now,
                                     uint32_t timeout_ticks, bool use_interrupt) {
    if (controller == NULL || controller->registers == NULL) {
        return SENSOR_BAD_ARGUMENT;
    }
    if (controller->state == SENSOR_WAITING) {
        return SENSOR_BUSY;
    }
    if (timeout_ticks == 0u) {
        timeout_ticks = SENSOR_DEFAULT_TIMEOUT;
    }
    controller->deadline = now + timeout_ticks;
    controller->state = SENSOR_WAITING;
    controller->registers->irq_clear = 0xffffffffu;
    uint32_t control = SENSOR_CONTROL_ENABLE | SENSOR_CONTROL_START;
    if (use_interrupt) {
        control |= SENSOR_CONTROL_IRQ_ENABLE;
    }
    controller->registers->control = control;
    return SENSOR_OK;
}

SensorResult sensor_controller_poll(SensorController *controller, uint32_t now,
                                    uint32_t spin_budget) {
    if (controller == NULL || controller->registers == NULL) {
        return SENSOR_BAD_ARGUMENT;
    }
    if (controller->state == SENSOR_READY) {
        return SENSOR_OK;
    }
    if (controller->state == SENSOR_FAILED) {
        return SENSOR_HARDWARE_ERROR;
    }
    if (controller->state != SENSOR_WAITING) {
        return SENSOR_EMPTY;
    }

    for (uint32_t attempt = 0u; attempt < spin_budget; ++attempt) {
        uint32_t status = controller->registers->status;
        if ((status & SENSOR_STATUS_FAULT) != 0u) {
            controller->stats.faults++;
            controller->state = SENSOR_FAILED;
            return SENSOR_HARDWARE_ERROR;
        }
        if ((status & SENSOR_STATUS_OVERRUN) != 0u) {
            controller->stats.overruns++;
            controller->registers->irq_clear = SENSOR_STATUS_OVERRUN;
        }
        if ((status & SENSOR_STATUS_READY) != 0u) {
            uint16_t raw = (uint16_t)(controller->registers->data & SENSOR_MAX_RAW);
            (void)queue_sample(controller, raw, now);
            controller->registers->irq_clear = SENSOR_STATUS_READY;
            controller->state = SENSOR_READY;
            return SENSOR_OK;
        }
    }
    if (deadline_passed(now, controller->deadline)) {
        controller->stats.timeouts++;
        controller->state = SENSOR_TIMED_OUT;
        controller->registers->control = SENSOR_CONTROL_ENABLE;
        return SENSOR_TIMEOUT;
    }
    return SENSOR_BUSY;
}

void sensor_controller_irq(SensorController *controller, uint32_t now) {
    if (controller == NULL || controller->registers == NULL) {
        return;
    }
    uint32_t pending = controller->registers->irq_status;
    controller->registers->irq_clear = pending;
    controller->irq_epoch++;

    if ((pending & SENSOR_STATUS_FAULT) != 0u) {
        controller->stats.faults++;
        controller->state = SENSOR_FAILED;
    } else if ((pending & SENSOR_STATUS_READY) != 0u &&
               controller->state == SENSOR_WAITING) {
        uint16_t raw = (uint16_t)(controller->registers->data & SENSOR_MAX_RAW);
        (void)queue_sample(controller, raw, now);
        controller->state = SENSOR_READY;
    }
    if ((pending & SENSOR_STATUS_OVERRUN) != 0u) {
        controller->stats.overruns++;
    }
}

SensorResult sensor_controller_take(SensorController *controller, SensorSample *sample) {
    if (controller == NULL || sample == NULL) {
        return SENSOR_BAD_ARGUMENT;
    }
    if (controller->tail == controller->head) {
        return SENSOR_EMPTY;
    }
    *sample = controller->queue[controller->tail];
    controller->tail = next_index(controller->tail);
    return SENSOR_OK;
}

SensorResult sensor_controller_set_calibration(SensorController *controller,
                                                int16_t offset, uint16_t gain_q8) {
    if (controller == NULL || gain_q8 == 0u) {
        return SENSOR_BAD_ARGUMENT;
    }
    if (controller->state == SENSOR_WAITING) {
        return SENSOR_BUSY;
    }
    controller->offset = offset;
    controller->gain_q8 = gain_q8;
    return SENSOR_OK;
}

SensorStats sensor_controller_stats(const SensorController *controller) {
    if (controller == NULL) {
        return (SensorStats){0};
    }
    return controller->stats;
}

void sensor_controller_stop(SensorController *controller) {
    if (controller == NULL || controller->registers == NULL) {
        return;
    }
    controller->registers->control = 0u;
    controller->registers->irq_clear = 0xffffffffu;
    controller->state = SENSOR_IDLE;
}
