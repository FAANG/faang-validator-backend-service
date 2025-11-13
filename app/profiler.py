# app/utils/profiler.py
import cProfile
import io
import pstats
import functools
import inspect
import time

def cprofiled(sortby: str = "cumtime", limit: int = 20, output_file: str | None = None):
    """
    Decorator for profiling sync or async functions with cProfile.
    Prints or saves results with total time in seconds/minutes.
    """
    def decorate(func):
        if inspect.iscoroutinefunction(func):
            # Async function
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                start = time.perf_counter()
                pr = cProfile.Profile()
                pr.enable()
                try:
                    return await func(*args, **kwargs)
                finally:
                    pr.disable()
                    elapsed = time.perf_counter() - start
                    s = io.StringIO()
                    stats = pstats.Stats(pr, stream=s).strip_dirs().sort_stats(sortby)
                    stats.print_stats(limit)

                    total_time_str = (
                        f"{elapsed:.3f} sec" if elapsed < 60 else f"{elapsed/60:.2f} min"
                    )
                    print(f"\n--- cProfile for async function {func.__name__} ---")
                    print(f"Total execution time: {total_time_str}")
                    print(s.getvalue())

                    if output_file:
                        stats.dump_stats(output_file)
            return async_wrapper

        else:
            # Sync function
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                start = time.perf_counter()
                pr = cProfile.Profile()
                pr.enable()
                try:
                    return func(*args, **kwargs)
                finally:
                    pr.disable()
                    elapsed = time.perf_counter() - start
                    s = io.StringIO()
                    stats = pstats.Stats(pr, stream=s).strip_dirs().sort_stats(sortby)
                    stats.print_stats(limit)

                    total_time_str = (
                        f"{elapsed:.3f} sec" if elapsed < 60 else f"{elapsed/60:.2f} min"
                    )
                    print(f"\n--- cProfile for function {func.__name__} ---")
                    print(f"Total execution time: {total_time_str}")
                    print(s.getvalue())

                    if output_file:
                        stats.dump_stats(output_file)
            return sync_wrapper
    return decorate



def human_seconds(t: float) -> str:
    return f"{t:.3f}s" if t < 60 else f"{t/60:.2f}m"

def print_pretty_profile(pr: cProfile.Profile, sortby="cumtime", limit=20, file_filter=None):
    """
    Pretty print cProfile stats with human-readable times and % of total.
    - sortby: 'cumtime' or 'tottime'
    - file_filter: show only rows whose filename contains this substring (optional)
    """
    s = io.StringIO()
    ps = pstats.Stats(pr, stream=s).strip_dirs().sort_stats(sortby)

    # collect rows
    rows = []
    total_time = getattr(ps, "total_tt", None)  # Python 3.11+
    if total_time is None:
        # fallback: take max cumtime across entries as an approximation of total runtime
        total_time = max((entry[3] for entry in ps.stats.values()), default=0.0)

    for func in ps.fcn_list:  # list sorted by sort_stats()
        cc, nc, tt, ct, callers = ps.stats[func]
        filename, lineno, funcname = func
        if file_filter and file_filter not in filename:
            continue
        rows.append({
            "file": filename.split("/")[-1],
            "line": lineno,
            "func": funcname,
            "ncalls": nc,
            "tottime": tt,
            "cumtime": ct,
        })

    # limit rows
    rows = rows[:limit]

    # print header
    print(f"{'ncalls':>7}  {'tottime':>10}  {'cumtime':>10}  {'%total':>7}  location")
    for r in rows:
        pct = (r["cumtime"] / total_time * 100.0) if total_time else 0.0
        print(f"{r['ncalls']:>7}  {human_seconds(r['tottime']):>10}  {human_seconds(r['cumtime']):>10}  {pct:6.1f}%  "
              f"{r['file']}:{r['line']}({r['func']})")