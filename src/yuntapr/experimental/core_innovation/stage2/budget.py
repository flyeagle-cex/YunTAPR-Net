"""Pure independent budget arithmetic, never a grant or an execution counter."""
import math


def paired_budget(*, train_population, dev_population, epochs, physical_batch,
                  validation_batch, loss_arms=1, seeds=1):
    numbers = (train_population, dev_population, epochs, physical_batch, validation_batch, loss_arms, seeds)
    if any(type(n) is not int or n <= 0 for n in numbers):
        raise ValueError('Explicit positive integer candidate budgets required')
    per_epoch = math.ceil(train_population/physical_batch)
    runs = 2*loss_arms*seeds
    return dict(status='PROPOSED_NOT_AUTHORIZED', models=['B3', 'B4'], matched_train_population=train_population,
        matched_dev_population=dev_population, physical_batch=physical_batch, accumulation=1,
        epochs=epochs, loss_arms=loss_arms, seeds=seeds, paired_runs=runs,
        optimizer_updates_per_epoch_per_run=per_epoch, optimizer_updates_per_run=per_epoch*epochs,
        new_independent_optimizer_attempt_cap=per_epoch*epochs*runs,
        validation_forward_batches=math.ceil(dev_population/validation_batch)*epochs*runs,
        validation_batch=validation_batch, replay_allowance=0, inherited_seed2027_budget_used=0)


def resources(*, parameters, measured_peak_allocated, measured_peak_reserved, measured_seconds,
              updates, validation_batches, io_seconds_per_train_batch=None, validation_peak_allocated=None):
    if min(parameters, measured_peak_allocated, measured_peak_reserved, measured_seconds, updates, validation_batches) <= 0:
        raise ValueError('Positive measured inputs required')
    # FP32 parameters/gradients/two AdamW moments: 16N bytes. Probe already holds
    # params+grad; add only two not-yet-allocated moments (8N) to its live peak.
    return dict(parameters=parameters, adamw_params_grad_moments_bytes=16*parameters,
        synthetic_peak_allocated_bytes=measured_peak_allocated, synthetic_peak_reserved_bytes=measured_peak_reserved,
        validation_batch8_synthetic_peak_allocated_bytes=validation_peak_allocated,
        allocation_plus_unmeasured_adamw_moments_bytes=measured_peak_allocated+8*parameters,
        compute_only_proxy_hours=updates*measured_seconds/3600,
        single_probe_seconds=measured_seconds, validation_batches=validation_batches,
        wall_time_estimate_hours=None if io_seconds_per_train_batch is None else updates*(measured_seconds+io_seconds_per_train_batch)/3600,
        limitations='Single synthetic forward/backward includes startup effects; no scientific loss, optimizer step, full meteorological validation or disk decoding measured. Compute proxy is not a reliable wall-time estimate.'+(' Validation batch 8 memory unverified.' if validation_peak_allocated is None else ' Batch-8 synthetic inference memory checked; metric aggregation and real decoding overhead unmeasured.'))
