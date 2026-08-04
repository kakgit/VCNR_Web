"""VCNR M-P2P transfer simulator.

This script tests the package-transfer rules without installing Android APKs.
It intentionally avoids real video files and uses fake encrypted chunk bytes.
"""

from __future__ import annotations

import argparse
import hashlib
import heapq
import json
import random
import secrets
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class User:
    user_id: str
    entitlements: set[tuple[str, str]]


@dataclass(frozen=True)
class TransferPackage:
    movie_id: str
    quality_code: str
    title: str
    root: Path
    manifest_path: Path
    chunk_names: list[str]


class TransferError(RuntimeError):
    pass


class RelayTransport:
    """Transport adapter used by the simulator.

    The final app can swap this shape with a backend relay, direct LAN, WebRTC,
    libp2p, or any other path. The receiver only trusts manifest hashes.
    """

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def publish_manifest(self, package: TransferPackage) -> None:
        shutil.copy2(package.manifest_path, self.root / "manifest.json")

    def has_manifest(self) -> bool:
        return (self.root / "manifest.json").exists()

    def read_manifest(self) -> dict:
        return json.loads((self.root / "manifest.json").read_text(encoding="utf-8"))

    def upload_chunk(self, sender_root: Path, chunk_name: str) -> None:
        destination = self.root / "chunks" / chunk_name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(sender_root / "encrypted" / chunk_name, destination)

    def available_chunks(self) -> set[str]:
        chunk_root = self.root / "chunks"
        if not chunk_root.exists():
            return set()
        return {path.name for path in chunk_root.iterdir() if path.is_file()}

    def download_chunk(self, chunk_name: str, receiver_root: Path) -> None:
        source = self.root / "chunks" / chunk_name
        if not source.exists():
            raise TransferError(f"relay is missing {chunk_name}")
        destination = receiver_root / "encrypted" / chunk_name
        destination.parent.mkdir(parents=True, exist_ok=True)
        temp_destination = destination.with_suffix(destination.suffix + ".part")
        shutil.copy2(source, temp_destination)
        temp_destination.replace(destination)

    def corrupt_chunk(self, chunk_name: str) -> None:
        chunk_path = self.root / "chunks" / chunk_name
        chunk_path.write_bytes(chunk_path.read_bytes() + b"corrupt")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def md5_file(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def create_fake_package(root: Path, movie_id: str, quality_code: str, chunks: int) -> TransferPackage:
    package_root = root / movie_id / quality_code
    encrypted_root = package_root / "encrypted"
    encrypted_root.mkdir(parents=True, exist_ok=True)

    chunk_names: list[str] = []
    manifest_chunks: list[dict] = []
    for index in range(1, chunks + 1):
        chunk_name = f"chunk-{index:04d}.vcnr"
        chunk_path = encrypted_root / chunk_name
        chunk_path.write_bytes(secrets.token_bytes(8192 + index))
        chunk_names.append(chunk_name)
        manifest_chunks.append(
            {
                "name": chunk_name,
                "size": chunk_path.stat().st_size,
                "encrypted_md5": md5_file(chunk_path),
                "encrypted_sha256": sha256_file(chunk_path),
            }
        )

    manifest = {
        "movie_id": movie_id,
        "quality_code": quality_code,
        "title": "Simulator Title",
        "chunks": manifest_chunks,
    }
    manifest_path = package_root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    return TransferPackage(
        movie_id=movie_id,
        quality_code=quality_code,
        title="Simulator Title",
        root=package_root,
        manifest_path=manifest_path,
        chunk_names=chunk_names,
    )


def require_entitlement(user: User, movie_id: str, quality_code: str) -> None:
    if (movie_id, quality_code) not in user.entitlements:
        raise TransferError(f"user {user.user_id} is not entitled to {movie_id}/{quality_code}")


def start_session(sender: User, receiver: User, package: TransferPackage, transport: RelayTransport) -> None:
    require_entitlement(sender, package.movie_id, package.quality_code)
    require_entitlement(receiver, package.movie_id, package.quality_code)
    transport.publish_manifest(package)


def local_chunk_names(root: Path) -> set[str]:
    chunk_root = root / "encrypted"
    if not chunk_root.exists():
        return set()
    return {path.name for path in chunk_root.iterdir() if path.is_file() and path.suffix == ".vcnr"}


def upload_missing_chunks(package: TransferPackage, transport: RelayTransport, limit: int | None = None) -> int:
    uploaded = 0
    relay_ready = transport.available_chunks()
    for chunk_name in package.chunk_names:
        if chunk_name in relay_ready:
            continue
        transport.upload_chunk(package.root, chunk_name)
        uploaded += 1
        if limit is not None and uploaded >= limit:
            break
    return uploaded


def verify_chunk(path: Path, expected: dict) -> None:
    if path.stat().st_size != expected["size"]:
        raise TransferError(f"{path.name} size mismatch")
    if md5_file(path) != expected["encrypted_md5"]:
        raise TransferError(f"{path.name} md5 mismatch")
    if sha256_file(path) != expected["encrypted_sha256"]:
        raise TransferError(f"{path.name} sha256 mismatch")


def receiver_sync(receiver_root: Path, transport: RelayTransport) -> tuple[int, int]:
    if not transport.has_manifest():
        raise TransferError("manifest has not been published")

    manifest = transport.read_manifest()
    receiver_root.mkdir(parents=True, exist_ok=True)
    (receiver_root / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    local_ready = local_chunk_names(receiver_root)
    relay_ready = transport.available_chunks()
    downloaded = 0

    for chunk in manifest["chunks"]:
        chunk_name = chunk["name"]
        destination = receiver_root / "encrypted" / chunk_name
        if chunk_name in local_ready:
            verify_chunk(destination, chunk)
            continue
        if chunk_name not in relay_ready:
            continue
        transport.download_chunk(chunk_name, receiver_root)
        verify_chunk(destination, chunk)
        downloaded += 1

    total = len(manifest["chunks"])
    ready = len(local_chunk_names(receiver_root))
    return downloaded, ready if ready <= total else total


def assert_complete(receiver_root: Path, expected_count: int) -> None:
    ready = local_chunk_names(receiver_root)
    if len(ready) != expected_count:
        raise TransferError(f"receiver has {len(ready)} of {expected_count} chunks")
    for path in receiver_root.glob("**/*"):
        if path.suffix.lower() == ".mp4":
            raise TransferError("receiver unexpectedly contains an unlocked mp4")


@dataclass
class SimSeeder:
    seeder_id: str
    available_chunks: set[str]
    bytes_per_second: int
    failure_probability: float = 0.0
    corrupt_probability: float = 0.0
    completed_count: int = 0
    bytes_served: int = 0
    failed_count: int = 0
    dead: bool = False
    chunks_served: set[str] = field(default_factory=set)


@dataclass
class SimServer:
    chunks: set[str]
    bytes_per_second: int


@dataclass
class SimChunkAssignment:
    chunk_name: str
    source_id: str
    source_type: str
    started_at: float
    virtual_duration_ms: int


class MultiSeederCoordinatorSimulator:
    """Simulates the VcnrMultiSeederCoordinator logic in pure Python.

    Models:
    - P2P-first: connect to N seeders in parallel (SimSeeder)
    - Server always on (SimServer) as fallback
    - Assign chunks to ready peers when they can serve them
    - If no peer can serve a chunk -> assign immediately to server
    - Timeout-based re-queueing: chunks assigned too long -> re-queue
    - Corrupt/failed chunks -> re-queue, increment source failure, fallback next peer or server
    - Refresh seeder pool periodically (mid-download new seeders appear)
    """

    def __init__(
        self,
        seeders: list[SimSeeder],
        server: SimServer,
        all_chunk_names: list[str],
        manifest_chunks: dict[str, dict],
        chunk_sizes: dict[str, int],
        receiver_root: Path,
        package_encrypted_root: Path,
        max_parallel_per_seeder: int = 2,
        chunk_timeout_ms: int = 45000,
        server_fallback_enabled: bool = True,
    ) -> None:
        self.seeders = {s.seeder_id: s for s in seeders}
        self.server = server
        self.all_chunk_names = sorted(all_chunk_names)
        self.manifest_chunks = manifest_chunks
        self.chunk_sizes = chunk_sizes
        self.receiver_root = receiver_root
        self.package_encrypted_root = package_encrypted_root
        self.encrypted_dir = receiver_root / "encrypted"
        self.encrypted_dir.mkdir(parents=True, exist_ok=True)
        self.max_parallel_per_seeder = max_parallel_per_seeder
        self.chunk_timeout_ms = chunk_timeout_ms
        self.server_fallback_enabled = server_fallback_enabled

        self.verified: set[str] = set()
        self.missing_queue: list[str] = []
        self.in_flight: dict[str, SimChunkAssignment] = {}
        self.active_peers: set[str] = set()

        self.from_peer_count: int = 0
        self.from_server_count: int = 0
        self.fallback_switches: int = 0
        self.last_source: str = "none"

        self._virtual_clock_ms: float = 0.0

    def _peer_source_count(self, source_id: str) -> int:
        return sum(1 for a in self.in_flight.values() if a.source_id == source_id)

    def _peers_with_chunk(self, chunk_name: str) -> list[SimSeeder]:
        out: list[SimSeeder] = []
        for s in self.seeders.values():
            if s.dead:
                continue
            if chunk_name not in s.available_chunks:
                continue
            if self._peer_source_count(s.seeder_id) >= self.max_parallel_per_seeder:
                continue
            out.append(s)
        out.sort(key=lambda s: (s.failed_count, s.completed_count, -s.bytes_per_second))
        return out

    def _queue_server_chunk(self, chunk_name: str) -> None:
        if chunk_name in self.in_flight:
            return
        if chunk_name in self.verified:
            return
        size = self.chunk_sizes[chunk_name]
        duration_ms = max(1, int(1000 * size / self.server.bytes_per_second))
        self.in_flight[chunk_name] = SimChunkAssignment(
            chunk_name=chunk_name,
            source_id="server",
            source_type="server",
            started_at=self._virtual_clock_ms,
            virtual_duration_ms=duration_ms,
        )

    def _assign_queued_chunks(self) -> None:
        deferred: list[str] = []
        while self.missing_queue:
            chunk_name = self.missing_queue.pop(0)
            if chunk_name in self.verified or chunk_name in self.in_flight:
                continue
            peers = self._peers_with_chunk(chunk_name)
            if peers:
                seeder = peers[0]
                size = self.chunk_sizes[chunk_name]
                duration_ms = max(1, int(1000 * size / seeder.bytes_per_second))
                self.in_flight[chunk_name] = SimChunkAssignment(
                    chunk_name=chunk_name,
                    source_id=seeder.seeder_id,
                    source_type="peer",
                    started_at=self._virtual_clock_ms,
                    virtual_duration_ms=duration_ms,
                )
                self.active_peers.add(seeder.seeder_id)
            elif self.server_fallback_enabled and chunk_name in self.server.chunks:
                self._queue_server_chunk(chunk_name)
            else:
                deferred.append(chunk_name)
        self.missing_queue = deferred + self.missing_queue

    def _expire_timeouts(self) -> None:
        expired = [c for c, a in self.in_flight.items() if (self._virtual_clock_ms - a.started_at) > self.chunk_timeout_ms]
        for chunk_name in expired:
            a = self.in_flight.pop(chunk_name)
            if a.source_type == "peer":
                seeder = self.seeders.get(a.source_id)
                if seeder is not None:
                    seeder.failed_count += 1
                    if seeder.failed_count >= 3:
                        seeder.dead = True
                        self.active_peers.discard(seeder.seeder_id)
            self.fallback_switches += 1
            if chunk_name not in self.verified:
                self.missing_queue.append(chunk_name)

    def _finish_chunk(self, chunk_name: str, source_id: str, source_type: str, corrupt: bool = False, failed: bool = False) -> bool:
        self.in_flight.pop(chunk_name, None)
        if failed or corrupt:
            if source_type == "peer":
                seeder = self.seeders.get(source_id)
                if seeder is not None:
                    seeder.failed_count += 1
                    if seeder.failed_count >= 3:
                        seeder.dead = True
                        self.active_peers.discard(seeder.seeder_id)
            if chunk_name not in self.verified:
                self.missing_queue.append(chunk_name)
            return False
        spec = self.manifest_chunks[chunk_name]
        size = self.chunk_sizes[chunk_name]
        source_path = self.package_encrypted_root / chunk_name
        if not source_path.exists():
            self.missing_queue.append(chunk_name)
            return False
        dest = self.encrypted_dir / chunk_name
        shutil.copy2(source_path, dest)
        if corrupt:
            dest.write_bytes(dest.read_bytes() + b"corrupt")
        try:
            verify_chunk(dest, spec)
        except TransferError:
            dest.unlink(missing_ok=True)
            if chunk_name not in self.verified:
                self.missing_queue.append(chunk_name)
            return False
        self.verified.add(chunk_name)
        self.last_source = "server" if source_type == "server" else f"peer:{source_id}"
        if source_type == "server":
            self.from_server_count += 1
        else:
            self.from_peer_count += 1
            seeder = self.seeders.get(source_id)
            if seeder is not None:
                seeder.completed_count += 1
                seeder.bytes_served += size
                seeder.chunks_served.add(chunk_name)
        return True

    def _advance_time(self, step_ms: int) -> None:
        self._virtual_clock_ms += step_ms
        finished: list[tuple[str, SimChunkAssignment]] = []
        for chunk_name, a in self.in_flight.items():
            if (self._virtual_clock_ms - a.started_at) >= a.virtual_duration_ms:
                finished.append((chunk_name, a))
        for chunk_name, a in finished:
            corrupt = False
            failed = False
            if a.source_type == "peer":
                seeder = self.seeders.get(a.source_id)
                if seeder is None or seeder.dead:
                    failed = True
                else:
                    if random.random() < seeder.failure_probability:
                        failed = True
                    if random.random() < seeder.corrupt_probability:
                        corrupt = True
            self._finish_chunk(chunk_name, a.source_id, a.source_type, corrupt=corrupt, failed=failed)

    def add_seeder(self, seeder: SimSeeder) -> None:
        self.seeders[seeder.seeder_id] = seeder

    def mark_seeder_dead(self, seeder_id: str) -> None:
        seeder = self.seeders.get(seeder_id)
        if seeder is None:
            return
        seeder.dead = True
        self.active_peers.discard(seeder_id)
        requeue = [c for c, a in self.in_flight.items() if a.source_id == seeder_id]
        for chunk_name in requeue:
            self.in_flight.pop(chunk_name, None)
            if chunk_name not in self.verified:
                self.missing_queue.append(chunk_name)

    def run(
        self,
        already_verified: set[str] | None = None,
        max_cycles: int = 20000,
        new_seeder_appear_at_cycle: int | None = None,
        new_seeder_factory=None,
        kill_seeder_at_cycle: tuple[int, str] | None = None,
    ) -> dict:
        if already_verified is not None:
            for c in already_verified:
                if c in self.manifest_chunks:
                    self.verified.add(c)
        self.missing_queue = [c for c in self.all_chunk_names if c not in self.verified]
        cycle = 0
        while cycle < max_cycles:
            cycle += 1
            if new_seeder_appear_at_cycle is not None and cycle == new_seeder_appear_at_cycle and new_seeder_factory is not None:
                ns = new_seeder_factory()
                self.add_seeder(ns)
            if kill_seeder_at_cycle is not None and cycle == kill_seeder_at_cycle[0]:
                self.mark_seeder_dead(kill_seeder_at_cycle[1])
            self._assign_queued_chunks()
            if self.server_fallback_enabled:
                self._assign_server_for_no_peer_servable_chunks()
            self._advance_time(step_ms=50)
            self._expire_timeouts()
            if len(self.verified) >= len(self.all_chunk_names):
                break
        return {
            "verified": len(self.verified),
            "total": len(self.all_chunk_names),
            "from_peer": self.from_peer_count,
            "from_server": self.from_server_count,
            "fallback_switches": self.fallback_switches,
            "cycles": cycle,
            "active_peers_final": len(self.active_peers),
            "last_source": self.last_source,
        }

    def _assign_server_for_no_peer_servable_chunks(self) -> None:
        if not self.server_fallback_enabled:
            return
        if not self.missing_queue:
            return
        any_peer_can = set()
        for c in self.missing_queue:
            for s in self.seeders.values():
                if s.dead:
                    continue
                if c in s.available_chunks:
                    any_peer_can.add(c)
                    break
        still_no_peer: list[str] = []
        processed: set[str] = set()
        round_robin: list[str] = []
        for c in self.missing_queue:
            if c in processed:
                continue
            processed.add(c)
            if c in any_peer_can:
                round_robin.append(c)
            else:
                still_no_peer.append(c)
        self.missing_queue = round_robin + still_no_peer[-1::-1]
        take = still_no_peer
        for chunk_name in take:
            if chunk_name in self.server.chunks:
                self._queue_server_chunk(chunk_name)


def _build_manifest_chunks_and_sizes(package: TransferPackage) -> tuple[dict[str, dict], dict[str, int]]:
    manifest = json.loads(package.manifest_path.read_text(encoding="utf-8"))
    by_name: dict[str, dict] = {}
    sizes: dict[str, int] = {}
    for chunk in manifest["chunks"]:
        by_name[chunk["name"]] = chunk
        sizes[chunk["name"]] = chunk["size"]
    return by_name, sizes


def run_case(name: str, action) -> bool:
    try:
        action()
    except Exception as exc:  # noqa: BLE001 - simulator should report all failures.
        print(f"FAIL {name}: {exc}")
        return False
    print(f"PASS {name}")
    return True


def run_simulator(keep_dir: bool) -> int:
    workspace = Path(tempfile.mkdtemp(prefix="vcnr-mp2p-"))
    if keep_dir:
        print(f"Simulator workspace: {workspace}")

    movie_id = "sim-title-1"
    quality_code = "1080p"
    sender_user = User("viewer-a", {(movie_id, quality_code)})
    receiver_same = User("viewer-a", {(movie_id, quality_code)})
    receiver_other_entitled = User("viewer-b", {(movie_id, quality_code)})
    receiver_other_blocked = User("viewer-c", set())

    def new_world(chunks: int = 12) -> tuple[TransferPackage, RelayTransport, Path]:
        package = create_fake_package(workspace / secrets.token_hex(4) / "sender", movie_id, quality_code, chunks)
        transport = RelayTransport(workspace / secrets.token_hex(4) / "relay")
        receiver_root = workspace / secrets.token_hex(4) / "receiver" / movie_id / quality_code
        return package, transport, receiver_root

    def complete_same_user() -> None:
        package, transport, receiver_root = new_world()
        start_session(sender_user, receiver_same, package, transport)
        upload_missing_chunks(package, transport)
        receiver_sync(receiver_root, transport)
        assert_complete(receiver_root, len(package.chunk_names))

    def resume_after_interruption() -> None:
        package, transport, receiver_root = new_world()
        start_session(sender_user, receiver_same, package, transport)
        upload_missing_chunks(package, transport, limit=5)
        receiver_sync(receiver_root, transport)
        upload_missing_chunks(package, transport)
        receiver_sync(receiver_root, transport)
        assert_complete(receiver_root, len(package.chunk_names))

    def cross_user_entitled() -> None:
        package, transport, receiver_root = new_world()
        start_session(sender_user, receiver_other_entitled, package, transport)
        upload_missing_chunks(package, transport)
        receiver_sync(receiver_root, transport)
        assert_complete(receiver_root, len(package.chunk_names))

    def cross_user_blocked() -> None:
        package, transport, _receiver_root = new_world()
        try:
            start_session(sender_user, receiver_other_blocked, package, transport)
        except TransferError:
            return
        raise TransferError("blocked receiver was allowed")

    def corrupt_chunk_rejected() -> None:
        package, transport, receiver_root = new_world()
        start_session(sender_user, receiver_same, package, transport)
        upload_missing_chunks(package, transport)
        transport.corrupt_chunk(package.chunk_names[0])
        try:
            receiver_sync(receiver_root, transport)
        except TransferError:
            return
        raise TransferError("corrupted chunk was accepted")

    def multiseeder_four_peers_p2p_first_complete() -> None:
        package, _transport, receiver_root = new_world(chunks=24)
        manifest_by_name, sizes = _build_manifest_chunks_and_sizes(package)
        all_names = package.chunk_names
        random.seed(42)
        seeders = [
            SimSeeder(f"seed-{i}", set(random.sample(all_names, k=min(len(all_names), 12 + i * 2))),
                      bytes_per_second=(i + 1) * 200_000)
            for i in range(4)
        ]
        server = SimServer(set(all_names), bytes_per_second=5_000_000)
        coordinator = MultiSeederCoordinatorSimulator(
            seeders=seeders,
            server=server,
            all_chunk_names=all_names,
            manifest_chunks=manifest_by_name,
            chunk_sizes=sizes,
            receiver_root=receiver_root,
            package_encrypted_root=package.root / "encrypted",
            server_fallback_enabled=True,
            chunk_timeout_ms=5000,
        )
        result = coordinator.run()
        if result["verified"] != len(all_names):
            raise TransferError(f"multi-seeder 4-peer incomplete: {result}")
        if result["from_peer"] < int(0.5 * len(all_names)):
            raise TransferError(f"expected peer-assisted delivery (>=50% from peers), got {result}")
        if result["from_server"] + result["from_peer"] != len(all_names):
            raise TransferError(f"source counts mismatched with verified: {result}")
        assert_complete(receiver_root, len(all_names))

    def multiseeder_zero_peers_server_fallback_only() -> None:
        package, _transport, receiver_root = new_world(chunks=16)
        manifest_by_name, sizes = _build_manifest_chunks_and_sizes(package)
        server = SimServer(set(package.chunk_names), bytes_per_second=4_000_000)
        coordinator = MultiSeederCoordinatorSimulator(
            seeders=[],
            server=server,
            all_chunk_names=package.chunk_names,
            manifest_chunks=manifest_by_name,
            chunk_sizes=sizes,
            receiver_root=receiver_root,
            package_encrypted_root=package.root / "encrypted",
            server_fallback_enabled=True,
            chunk_timeout_ms=5000,
        )
        result = coordinator.run()
        if result["verified"] != len(package.chunk_names):
            raise TransferError(f"zero-peer server-only fallback failed: {result}")
        if result["from_peer"] != 0:
            raise TransferError(f"zero-peer case should have no peer bytes: {result}")
        if result["from_server"] != len(package.chunk_names):
            raise TransferError(f"zero-peer case should all come from server: {result}")
        assert_complete(receiver_root, len(package.chunk_names))

    def multiseeder_seeder_dies_mid_download_server_fills_gaps() -> None:
        package, _transport, receiver_root = new_world(chunks=30)
        manifest_by_name, sizes = _build_manifest_chunks_and_sizes(package)
        all_names = package.chunk_names
        random.seed(7)
        seeders = [
            SimSeeder("seed-fast", set(all_names), bytes_per_second=4_000_000),
            SimSeeder("seed-steady", set(random.sample(all_names, k=22)), bytes_per_second=1_500_000),
            SimSeeder("seed-light", set(random.sample(all_names, k=16)), bytes_per_second=900_000),
        ]
        server = SimServer(set(all_names), bytes_per_second=6_000_000)
        coordinator = MultiSeederCoordinatorSimulator(
            seeders=seeders,
            server=server,
            all_chunk_names=all_names,
            manifest_chunks=manifest_by_name,
            chunk_sizes=sizes,
            receiver_root=receiver_root,
            package_encrypted_root=package.root / "encrypted",
            server_fallback_enabled=True,
            max_parallel_per_seeder=2,
            chunk_timeout_ms=5000,
        )
        result = coordinator.run(kill_seeder_at_cycle=(25, "seed-fast"))
        if result["verified"] != len(all_names):
            raise TransferError(f"seeder-die mid-download failed completion: {result}")
        if result["from_server"] < 1:
            raise TransferError(f"expected server to fill gaps after seeder died, got {result}")
        assert_complete(receiver_root, len(all_names))

    def multiseeder_new_seeder_appears_mid_download() -> None:
        package, _transport, receiver_root = new_world(chunks=28)
        manifest_by_name, sizes = _build_manifest_chunks_and_sizes(package)
        all_names = package.chunk_names
        random.seed(11)
        slow_seeder = SimSeeder("seed-slow", set(random.sample(all_names, k=18)), bytes_per_second=200_000)
        server = SimServer(set(all_names), bytes_per_second=5_000_000)

        def new_seeder_factory() -> SimSeeder:
            return SimSeeder("seed-fast-arrives", set(all_names), bytes_per_second=5_000_000)

        coordinator = MultiSeederCoordinatorSimulator(
            seeders=[slow_seeder],
            server=server,
            all_chunk_names=all_names,
            manifest_chunks=manifest_by_name,
            chunk_sizes=sizes,
            receiver_root=receiver_root,
            package_encrypted_root=package.root / "encrypted",
            server_fallback_enabled=False,
            chunk_timeout_ms=5000,
        )
        result = coordinator.run(
            new_seeder_appear_at_cycle=30,
            new_seeder_factory=new_seeder_factory,
        )
        if result["verified"] != len(all_names):
            raise TransferError(f"new-seeder appears mid-download incomplete: {result}")
        if "seed-fast-arrives" not in coordinator.seeders:
            raise TransferError(f"new seeder was not added to pool: {result}")
        fast = coordinator.seeders["seed-fast-arrives"]
        if fast.completed_count < 1:
            raise TransferError(f"new fast seeder should have contributed at least 1 chunk: {result}")
        assert_complete(receiver_root, len(all_names))

    def multiseeder_corrupt_seeder_banned_server_cover() -> None:
        package, _transport, receiver_root = new_world(chunks=40)
        manifest_by_name, sizes = _build_manifest_chunks_and_sizes(package)
        all_names = package.chunk_names
        random.seed(13)
        bad_seeder = SimSeeder("seed-bad", set(all_names), bytes_per_second=3_000_000, corrupt_probability=1.0, failure_probability=0.0)
        honest = SimSeeder("seed-good", set(random.sample(all_names, k=28)), bytes_per_second=1_200_000)
        server = SimServer(set(all_names), bytes_per_second=5_000_000)
        coordinator = MultiSeederCoordinatorSimulator(
            seeders=[bad_seeder, honest],
            server=server,
            all_chunk_names=all_names,
            manifest_chunks=manifest_by_name,
            chunk_sizes=sizes,
            receiver_root=receiver_root,
            package_encrypted_root=package.root / "encrypted",
            server_fallback_enabled=True,
            chunk_timeout_ms=5000,
            max_parallel_per_seeder=3,
        )
        result = coordinator.run()
        if result["verified"] != len(all_names):
            raise TransferError(f"corrupt seeder scenario failed: {result}")
        if bad_seeder.dead is not True and bad_seeder.failed_count < 3:
            raise TransferError(f"corrupt seeder should be banned (>2 fails) or already banned: fails={bad_seeder.failed_count} dead={bad_seeder.dead}")
        assert_complete(receiver_root, len(all_names))

    checks = [
        run_case("same-user complete transfer", complete_same_user),
        run_case("interrupted transfer resumes missing chunks", resume_after_interruption),
        run_case("different entitled user can receive encrypted package", cross_user_entitled),
        run_case("different non-entitled user is blocked", cross_user_blocked),
        run_case("corrupted relay chunk is rejected", corrupt_chunk_rejected),
        run_case("multi-seeder: 4 peers P2P first, server backup", multiseeder_four_peers_p2p_first_complete),
        run_case("multi-seeder: 0 seeders -> pure server fallback", multiseeder_zero_peers_server_fallback_only),
        run_case("multi-seeder: seeder dies mid-download, server fills gaps", multiseeder_seeder_dies_mid_download_server_fills_gaps),
        run_case("multi-seeder: new seeder appears mid-download (P2P only)", multiseeder_new_seeder_appears_mid_download),
        run_case("multi-seeder: corrupt seeder banned, honest + server cover", multiseeder_corrupt_seeder_banned_server_cover),
    ]

    if not keep_dir:
        shutil.rmtree(workspace, ignore_errors=True)

    return 0 if all(checks) else 1


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run VCNR M-P2P transfer simulator checks.")
    parser.add_argument("--keep-dir", action="store_true", help="Keep the generated simulator workspace.")
    args = parser.parse_args(list(argv) if argv is not None else None)
    return run_simulator(keep_dir=args.keep_dir)


if __name__ == "__main__":
    raise SystemExit(main())
