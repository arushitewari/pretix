#
# This file is part of pretix (Community Edition).
# Refactored for CSCI 630 Project 3 — Issue #85
# Anti-pattern: Cargo Cult Programming (repeated `if settings.HAS_REDIS` guards)
# Design Pattern: Facade — RedisBackend encapsulates all Redis interaction
#

import json
import math
import time
from collections import defaultdict

from django.apps import apps
from django.conf import settings
from django.db import connection

from pretix.base.models import Event, Invoice, Order, OrderPosition, Organizer
from pretix.celery_app import app

# ---------------------------------------------------------------------------
# BEFORE (cargo cult pattern):
#
#   def _inc_in_redis(self, key, amount, pipeline=None):
#       if settings.HAS_REDIS:           # <-- repeated guard everywhere
#           if not pipeline:
#               pipeline = redis
#           pipeline.hincrbyfloat(REDIS_KEY, key, amount)
#
#   def _set_in_redis(self, key, value, pipeline=None):
#       if settings.HAS_REDIS:           # <-- duplicated again
#           ...
#
#   def _get_redis_pipeline(self):
#       if settings.HAS_REDIS:           # <-- duplicated again
#           return redis.pipeline()
#
#   def _execute_redis_pipeline(self, pipeline):
#       if settings.HAS_REDIS:           # <-- duplicated again
#           return pipeline.execute()
#
# Every method that touches Redis duplicated the same availability guard,
# with no single authoritative place to find "how does Redis work here?".
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# AFTER: Facade pattern — one class owns all Redis interaction.
# The HAS_REDIS guard lives in exactly one place (the facade).
# Callers never need to know whether Redis is available.
# ---------------------------------------------------------------------------

REDIS_KEY = "pretix_metrics"
_INF = float("inf")
_MINUS_INF = float("-inf")


class RedisBackend:
    """
    Facade over the Redis connection used by the metrics subsystem.

    Responsibilities:
    - Holds the single Redis connection (when available).
    - Exposes inc(), set(), pipeline(), and execute_pipeline() without
      requiring callers to check HAS_REDIS themselves.
    - When Redis is unavailable, all operations are silent no-ops so the
      rest of the metrics code is unconditionally simple.

    This eliminates the repeated `if settings.HAS_REDIS` guard that
    previously appeared in every Metric method (cargo cult duplication).
    """

    def __init__(self):
        self._redis = None
        if settings.HAS_REDIS:
            import django_redis
            self._redis = django_redis.get_redis_connection("redis")

    @property
    def available(self):
        return self._redis is not None

    def inc(self, key, amount, pipeline=None):
        if not self.available:
            return
        target = pipeline if pipeline is not None else self._redis
        target.hincrbyfloat(REDIS_KEY, key, amount)

    def set(self, key, value, pipeline=None):
        if not self.available:
            return
        target = pipeline if pipeline is not None else self._redis
        target.hset(REDIS_KEY, key, value)

    def pipeline(self):
        if not self.available:
            return None
        return self._redis.pipeline()

    def execute_pipeline(self, pipeline):
        if not self.available or pipeline is None:
            return
        return pipeline.execute()

    def hscan_iter(self, count=1000):
        """Iterate over all metric keys stored in Redis."""
        if not self.available:
            return iter([])
        return self._redis.hscan_iter(REDIS_KEY, count=count)


# Module-level singleton — one facade instance for the whole process.
_redis_backend = RedisBackend()


def _float_to_go_string(d):
    if d == _INF:
        return '+Inf'
    elif d == _MINUS_INF:
        return '-Inf'
    elif math.isnan(d):
        return 'NaN'
    else:
        return repr(float(d))


class Metric(object):
    """Base Metrics Object"""

    def __init__(self, name, helpstring, labelnames=None):
        self.name = name
        self.helpstring = helpstring
        self.labelnames = labelnames or []

    def __repr__(self):
        return self.name + "{" + ",".join(self.labelnames) + "}"

    def _check_label_consistency(self, labels):
        for labelname in self.labelnames:
            if labelname not in labels:
                raise ValueError("Label {0} not specified.".format(labelname))
        if len(labels) != len(self.labelnames):
            raise ValueError("Unknown labels used: {}".format(", ".join(set(labels) - set(self.labelnames))))

    def _construct_metric_identifier(self, metricname, labels=None, labelnames=None):
        if not labels:
            return metricname
        named_labels = []
        for labelname in (labelnames or self.labelnames):
            named_labels.append('{}="{}"'.format(labelname, labels[labelname]))
        return metricname + "{" + ",".join(named_labels) + "}"

    # ---------------------------------------------------------------------------
    # AFTER: No HAS_REDIS guard here — the facade absorbs it.
    # ---------------------------------------------------------------------------
    def _inc_in_redis(self, key, amount, pipeline=None):
        _redis_backend.inc(key, amount, pipeline)

    def _set_in_redis(self, key, value, pipeline=None):
        _redis_backend.set(key, value, pipeline)

    def _get_redis_pipeline(self):
        return _redis_backend.pipeline()

    def _execute_redis_pipeline(self, pipeline):
        _redis_backend.execute_pipeline(pipeline)


class Counter(Metric):
    def inc(self, amount=1, **kwargs):
        if amount < 0:
            raise ValueError("Counter cannot be increased by negative values.")
        self._check_label_consistency(kwargs)
        fullmetric = self._construct_metric_identifier(self.name, kwargs)
        self._inc_in_redis(fullmetric, amount)


class Gauge(Metric):
    def set(self, value=1, **kwargs):
        self._check_label_consistency(kwargs)
        fullmetric = self._construct_metric_identifier(self.name, kwargs)
        self._set_in_redis(fullmetric, value)

    def inc(self, amount=1, **kwargs):
        if amount < 0:
            raise ValueError("Amount must be greater than zero. Otherwise use dec().")
        self._check_label_consistency(kwargs)
        fullmetric = self._construct_metric_identifier(self.name, kwargs)
        self._inc_in_redis(fullmetric, amount)

    def dec(self, amount=1, **kwargs):
        if amount < 0:
            raise ValueError("Amount must be greater than zero. Otherwise use inc().")
        self._check_label_consistency(kwargs)
        fullmetric = self._construct_metric_identifier(self.name, kwargs)
        self._inc_in_redis(fullmetric, amount * -1)


class Histogram(Metric):
    def __init__(self, name, helpstring, labelnames=None,
                 buckets=(.005, .01, .025, .05, .075, .1, .25, .5, .75, 1.0, 2.5, 5.0, 7.5, 10.0, 30.0, _INF)):
        if list(buckets) != sorted(buckets):
            raise ValueError('Buckets not in sorted order')
        if buckets and buckets[-1] != _INF:
            buckets.append(_INF)
        if len(buckets) < 2:
            raise ValueError('Must have at least two buckets')
        self.buckets = buckets
        super().__init__(name, helpstring, labelnames)

    def observe(self, amount, **kwargs):
        if amount < 0:
            raise ValueError("Amount must be greater than zero.")
        self._check_label_consistency(kwargs)
        pipe = self._get_redis_pipeline()
        countmetric = self._construct_metric_identifier(self.name + '_count', kwargs)
        self._inc_in_redis(countmetric, 1, pipeline=pipe)
        summetric = self._construct_metric_identifier(self.name + '_sum', kwargs)
        self._inc_in_redis(summetric, amount, pipeline=pipe)
        kwargs_le = dict(kwargs.items())
        for i, bound in enumerate(self.buckets):
            if amount <= bound:
                kwargs_le['le'] = _float_to_go_string(bound)
                bmetric = self._construct_metric_identifier(
                    self.name + '_bucket', kwargs_le,
                    labelnames=self.labelnames + ["le"]
                )
                self._inc_in_redis(bmetric, 1, pipeline=pipe)
        self._execute_redis_pipeline(pipe)


def estimate_count_fast(type):
    if 'postgres' in settings.DATABASES['default']['ENGINE']:
        cursor = connection.cursor()
        cursor.execute("select reltuples from pg_class where relname='%s';" % type._meta.db_table)
        row = cursor.fetchone()
        if not row:
            return 0
        return int(row[0])
    else:
        return type.objects.count()


def metric_values():
    metrics = defaultdict(dict)

    # AFTER: facade call — no guard needed here
    for key, value in _redis_backend.hscan_iter(count=1000):
        dkey = key.decode("utf-8")
        splitted = dkey.split("{", 2)
        value = float(value.decode("utf-8"))
        if len(splitted) == 1:
            metrics[splitted[0]][""] = value
        else:
            metrics[splitted[0]]["{" + splitted[1]] = value

    aliases = {
        'pretix_view_requests_total': 'pretix_view_duration_seconds_count'
    }
    for a, atarget in aliases.items():
        metrics[a] = metrics[atarget]

    exact_tables = [Order, OrderPosition, Invoice, Event, Organizer]
    for m in apps.get_models():
        if any(issubclass(m, p) for p in exact_tables):
            metrics['pretix_model_instances']['{model="%s"}' % m._meta] = m.objects.count()
        else:
            metrics['pretix_model_instances']['{model="%s"}' % m._meta] = estimate_count_fast(m)

    if settings.HAS_CELERY:
        channel = app.broker_connection().channel()
        if hasattr(channel, 'client') and channel.client is not None:
            client = channel.client
            priority_steps = settings.CELERY_BROKER_TRANSPORT_OPTIONS.get("priority_steps", [0])
            sep = settings.CELERY_BROKER_TRANSPORT_OPTIONS.get("sep", ":")
            for q in settings.CELERY_TASK_QUEUES:
                queue_lengths = []
                queue_delays = []
                for prio in priority_steps:
                    qname = f"{q.name}{sep}{prio}" if prio else q.name
                    queue_length = client.llen(qname)
                    queue_lengths.append(queue_length)
                    oldest_queue_item = client.lindex(qname, -1)
                    if oldest_queue_item:
                        ldata = json.loads(oldest_queue_item)
                        oldest_item_age = time.time() - ldata.get('created', 0)
                        queue_delays.append(oldest_item_age)
                metrics['pretix_celery_tasks_queued_count']['{queue="%s"}' % q.name] = sum(queue_lengths)
                metrics['pretix_celery_tasks_queued_age_seconds']['{queue="%s"}' % q.name] = (
                    max(queue_delays) if queue_delays else 0
                )

    return metrics


# Provided metrics (unchanged from original)
pretix_view_duration_seconds = Histogram(
    "pretix_view_duration_seconds", "Return time of views.", ["status_code", "method", "url_name"])
pretix_task_runs_total = Counter(
    "pretix_task_runs_total", "Total calls to a celery task", ["task_name", "status"])
pretix_task_duration_seconds = Histogram(
    "pretix_task_duration_seconds", "Call time of a celery task", ["task_name"])
pretix_successful_logins = Counter("pretix_logins_successful", "Successful logins", [])
pretix_failed_logins = Counter("pretix_logins_failed", "Failed logins", ["reason"])
