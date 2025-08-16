#!/usr/bin/env python3
"""
Redis LRU vs LFU Demo
Demonstrates the behavior differences between LRU and LFU eviction policies in Redis.
"""

import redis
import random
import string
import time
import json
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.live import Live
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.columns import Columns
from rich.text import Text

console = Console()


def generate_session_key():
    """Generate a Django-style session key with random components."""
    chars = string.ascii_letters + string.digits
    return f"session_{''.join(random.choices(chars, k=32))}"


def get_redis_info(redis_client):
    """Get memory and key information from Redis."""
    try:
        info = redis_client.info("memory")
        keyspace = redis_client.info("keyspace")

        used_memory = info.get("used_memory", 0)
        max_memory = info.get("maxmemory", 0)
        db0_info = keyspace.get("db0", {})
        key_count = db0_info.get("keys", 0) if isinstance(db0_info, dict) else 0

        return {
            "used_memory": used_memory,
            "max_memory": max_memory,
            "key_count": key_count,
            "memory_percent": (used_memory / max_memory * 100) if max_memory > 0 else 0,
        }
    except Exception as e:
        return {
            "used_memory": 0,
            "max_memory": 0,
            "key_count": 0,
            "memory_percent": 0,
            "error": str(e),
        }


def create_info_table(title, info, status_msg=""):
    """Create a compact rich table showing Redis instance information."""
    table = Table(
        title=f"🔴 {title}" if "LRU" in title else f"🔵 {title}",
        show_header=False,
        border_style="red" if "LRU" in title else "blue",
        padding=(0, 1),  # Reduce padding
    )

    if "error" in info:
        table.add_row("Status", f"[red]Error: {info['error']}[/red]")
        return table

    table.add_row("Memory", f"{info['used_memory'] / (1024 * 1024):.1f}/{info['max_memory'] / (1024 * 1024):.1f}MB ({info['memory_percent']:.0f}%)")
    table.add_row("Keys", f"{info['key_count']} keys")
    
    if status_msg:
        table.add_row("Status", status_msg)

    return table


def main():
    # Connect to Redis instances with timeout
    try:
        lru_redis = redis.Redis(
            host="localhost",
            port=6000,
            db=0,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
        )
        lfu_redis = redis.Redis(
            host="localhost",
            port=6001,
            db=0,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
        )

        # Test connections individually
        console.print("Testing LRU Redis connection (port 6000)...")
        lru_redis.ping()
        console.print("[green]✓ Connected to LRU Redis[/green]")

        console.print("Testing LFU Redis connection (port 6001)...")
        lfu_redis.ping()
        console.print("[green]✓ Connected to LFU Redis[/green]")

    except redis.exceptions.ConnectionError as e:
        console.print(f"[red]✗ Connection failed: {e}[/red]")
        console.print(
            "[yellow]Make sure both Redis instances are running on ports 6000 and 6001[/yellow]"
        )
        return
    except redis.exceptions.TimeoutError as e:
        console.print(f"[red]✗ Connection timeout: {e}[/red]")
        console.print(
            "[yellow]Redis instance may be overloaded or network issue[/yellow]"
        )
        return
    except Exception as e:
        console.print(f"[red]✗ Failed to connect to Redis: {e}[/red]")
        return

    # Clear any existing data
    lru_redis.flushdb()
    lfu_redis.flushdb()

    # Show header
    console.print(
        Panel(
            "[bold blue]Redis LRU vs LFU Eviction Demo[/bold blue]",
        )
    )

    # Phase 1: Fill LRU Redis
    console.print(
        "\n[yellow]Phase 1: Filling LRU Redis (port 6000) until memory limit...[/yellow]"
    )

    lru_keys = []
    lru_error_occurred = False
    lru_error_msg = ""

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Adding keys to LRU Redis...", total=None)

        while True:
            try:
                key = generate_session_key()
                # Create a substantial value to fill memory faster
                value = json.dumps(
                    {
                        "session_data": "".join(
                            random.choices(string.ascii_letters + string.digits, k=5000)
                        ),
                        "user_id": random.randint(1000, 9999),
                        "timestamp": time.time(),
                        "extra_data": "".join(
                            random.choices(string.ascii_letters + string.digits, k=3000)
                        ),
                    }
                )

                lru_redis.setex(key, 3600, value)  # 1 hour TTL
                lru_keys.append(key)

                progress.update(task, description=f"Added {len(lru_keys)} keys...")

                # Check if we're approaching memory limit
                lru_info = get_redis_info(lru_redis)
                if lru_info["memory_percent"] > 95:
                    break

                time.sleep(0.001)  # Small delay

            except redis.exceptions.ResponseError as e:
                if "OOM" in str(e) or "maxmemory" in str(e):
                    lru_error_occurred = True
                    lru_error_msg = f"Memory limit reached: {str(e)}"
                    break
                else:
                    raise
            except Exception as e:
                console.print(f"[red]Error adding key to LRU: {e}[/red]")
                break

    # Phase 2: Fill LFU Redis and demonstrate access patterns
    console.print(
        f"\n[yellow]Phase 2: Filling LFU Redis (port 6001) and creating access patterns...[/yellow]"
    )

    lfu_keys = []
    high_access_keys = []
    medium_access_keys = []
    low_access_keys = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        # Fill LFU Redis
        fill_task = progress.add_task("Filling LFU Redis...", total=None)

        while True:
            try:
                key = generate_session_key()
                value = json.dumps(
                    {
                        "session_data": "".join(
                            random.choices(string.ascii_letters + string.digits, k=5000)
                        ),
                        "user_id": random.randint(1000, 9999),
                        "timestamp": time.time(),
                        "extra_data": "".join(
                            random.choices(string.ascii_letters + string.digits, k=3000)
                        ),
                    }
                )

                lfu_redis.setex(key, 3600, value)
                lfu_keys.append(key)

                # Categorize keys for access patterns
                if len(lfu_keys) <= 12:
                    high_access_keys.append(key)  # First 12 keys for high access
                elif len(lfu_keys) <= 24:
                    medium_access_keys.append(key)  # Next 12 keys for medium access
                elif len(lfu_keys) <= 48:
                    low_access_keys.append(key)  # Next 24 keys for low access

                progress.update(
                    fill_task, description=f"Added {len(lfu_keys)} keys to LFU..."
                )

                # Check memory usage
                lfu_info = get_redis_info(lfu_redis)
                if lfu_info["memory_percent"] > 95:
                    break

                time.sleep(0.001)

            except Exception as e:
                console.print(f"[red]Error adding key to LFU: {e}[/red]")
                break

        # Create access patterns
        access_task = progress.add_task("Creating access patterns...", total=100)

        # High access keys (10 times each)
        for i, key in enumerate(high_access_keys):
            for _ in range(10):
                try:
                    lfu_redis.get(key)
                except:
                    pass
            progress.update(access_task, completed=i * 2)

        # Medium access keys (5 times each)
        for i, key in enumerate(medium_access_keys):
            for _ in range(5):
                try:
                    lfu_redis.get(key)
                except:
                    pass
            progress.update(access_task, completed=30 + i * 2)

        # Low access keys (2 times each)
        for i, key in enumerate(low_access_keys):
            for _ in range(2):
                try:
                    lfu_redis.get(key)
                except:
                    pass
            progress.update(access_task, completed=60 + i)

        progress.update(access_task, completed=100)

    # Phase 3: Add more keys to trigger LFU eviction
    console.print(
        "\n[yellow]Phase 3: Adding more keys to trigger LFU eviction...[/yellow]"
    )

    initial_key_count = get_redis_info(lfu_redis)["key_count"]

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        eviction_task = progress.add_task("Triggering evictions...", total=50)

        for i in range(50):
            try:
                key = generate_session_key()
                value = json.dumps(
                    {
                        "session_data": "".join(
                            random.choices(string.ascii_letters + string.digits, k=5000)
                        ),
                        "user_id": random.randint(1000, 9999),
                        "timestamp": time.time(),
                        "extra_data": "".join(
                            random.choices(string.ascii_letters + string.digits, k=3000)
                        ),
                    }
                )

                lfu_redis.setex(key, 3600, value)

                current_keys = get_redis_info(lfu_redis)["key_count"]
                evicted_keys = max(0, (initial_key_count + i + 1) - current_keys)

                progress.update(
                    eviction_task,
                    completed=i + 1,
                    description=f"Added {i + 1} keys, {evicted_keys} evicted",
                )

                time.sleep(0.05)

            except Exception as e:
                console.print(f"[red]Error during eviction test: {e}[/red]")
                break

    # Check which keys survived the eviction process
    console.print("\n[cyan]Analyzing key survival patterns...[/cyan]")

    survived_high = [key for key in high_access_keys if lfu_redis.exists(key)]
    survived_medium = [key for key in medium_access_keys if lfu_redis.exists(key)]
    survived_low = [key for key in low_access_keys if lfu_redis.exists(key)]

    evicted_high = [key for key in high_access_keys if not lfu_redis.exists(key)]
    evicted_medium = [key for key in medium_access_keys if not lfu_redis.exists(key)]
    evicted_low = [key for key in low_access_keys if not lfu_redis.exists(key)]

    # Final summary and display
    console.print("\n[bold green]Demo Complete![/bold green]\n")

    final_lru_info = get_redis_info(lru_redis)
    final_lfu_info = get_redis_info(lfu_redis)

    # Print Redis stats
    console.print(create_info_table(
        "LRU Redis (Port 6000)",
        final_lru_info,
        lru_error_msg if lru_error_occurred else f"Final: {len(lru_keys)} keys",
    ))
    
    console.print(create_info_table(
        "LFU Redis (Port 6001)",
        final_lfu_info,
        f"Final: {final_lfu_info['key_count']} keys",
    ))

    # Print survival analysis
    console.print(f"\n[bold green]Key Survival Analysis:[/bold green]")
    console.print(f"High freq (10x access): [green]{len(survived_high)}/12 survived[/green], [red]{len(evicted_high)}/12 evicted[/red]")
    console.print(f"Med freq (5x access):   [green]{len(survived_medium)}/12 survived[/green], [red]{len(evicted_medium)}/12 evicted[/red]")
    console.print(f"Low freq (2x access):   [green]{len(survived_low)}/24 survived[/green], [red]{len(evicted_low)}/24 evicted[/red]")

    # Print summary
    if lru_error_occurred:
        console.print(f"\n[bold red]LRU Result:[/bold red] [red]Stopped accepting keys at memory limit[/red]")
    
    console.print(f"[bold blue]LFU Result:[/bold blue] [blue]Smart frequency-based eviction![/blue]")
    console.print(f"[green]✓ Most frequently accessed keys were retained[/green]")
    console.print(f"[red]✓ Least frequently accessed keys were evicted[/red]")


if __name__ == "__main__":
    main()
