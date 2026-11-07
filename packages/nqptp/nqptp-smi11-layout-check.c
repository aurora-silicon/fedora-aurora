/* Aurora 2026-10-25: nqptp 1.2.9's shared memory layout, checked at build time and run time.
 * shairport-sync-4.3.7-nqptp-smi11.patch asserts the same numbers on the reader side. */
#include <stddef.h>
#include <stdio.h>
#include "nqptp-shm-structures.h"

_Static_assert(NQPTP_SHM_STRUCTURES_VERSION == 11, "smi11");
_Static_assert(sizeof(shm_structure_set) == 40, "record size");
_Static_assert(offsetof(shm_structure_set, master_clock_id) == 0, "layout");
_Static_assert(offsetof(shm_structure_set, local_time) == 8, "layout");
_Static_assert(offsetof(shm_structure_set, local_to_master_time_offset) == 16, "layout");
_Static_assert(offsetof(shm_structure_set, clock_change_offset) == 24, "layout");
_Static_assert(offsetof(shm_structure_set, master_clock_start_time) == 32, "layout");
_Static_assert(offsetof(struct shm_structure, version) == 0, "layout");
_Static_assert(offsetof(struct shm_structure, main) == 8, "layout");
_Static_assert(offsetof(struct shm_structure, secondary) == 48, "layout");
_Static_assert(sizeof(struct shm_structure) == 88, "region size");

int main(void) {
  printf("smi%d record=%zu region=%zu main@%zu secondary@%zu clock_change_offset@%zu\n",
         NQPTP_SHM_STRUCTURES_VERSION, sizeof(shm_structure_set), sizeof(struct shm_structure),
         offsetof(struct shm_structure, main), offsetof(struct shm_structure, secondary),
         offsetof(shm_structure_set, clock_change_offset));
  return 0;
}
