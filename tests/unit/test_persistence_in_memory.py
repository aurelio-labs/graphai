import pytest

from graphai.persistence import (
    SimpleStatePersistence,
    FullStatePersistence,
    NodeSnapshot,
    EndSnapshot,
)


class DummyNode:
    name = "dummy_node"


@pytest.mark.asyncio
async def test_simple_state_persistence_happy_path():
    p = SimpleStatePersistence()

    # snapshot next node
    state = {"x": 1}
    await p.snapshot_node(state=state, next_node=DummyNode)
    assert isinstance(p.last_snapshot, NodeSnapshot)
    assert p.last_snapshot.status == "created"
    assert p.last_snapshot.node_name == "dummy_node"
    assert p.last_snapshot.node is DummyNode
    # Pydantic model creates its own container; check equality
    assert p.last_snapshot.state == state

    # load_next promotes to pending
    snap = await p.load_next()
    assert isinstance(snap, NodeSnapshot)
    assert snap.status == "pending"

    sid = p.peek_last_id()
    assert isinstance(sid, str)

    # record_run marks success and captures timing
    async with p.record_run(sid):
        pass
    assert p.last_snapshot.status == "success"
    assert p.last_snapshot.duration is not None
    assert p.last_snapshot.start_ts is not None

    # idempotent snapshot_node_if_new when id matches
    prev_id = p.last_snapshot.id
    await p.snapshot_node_if_new(prev_id, state={"y": 2}, next_node=DummyNode)
    # unchanged because ids matched
    assert p.last_snapshot.id == prev_id
    assert isinstance(p.last_snapshot, NodeSnapshot)

    # end snapshot replaces last_snapshot
    await p.snapshot_end(state={"final": True}, result={"ok": 1})
    assert isinstance(p.last_snapshot, EndSnapshot)
    assert p.last_snapshot.result == {"ok": 1}


@pytest.mark.asyncio
async def test_simple_state_persistence_error_path():
    p = SimpleStatePersistence()
    await p.snapshot_node(state={}, next_node=DummyNode)
    sid = p.peek_last_id()
    assert isinstance(sid, str)

    with pytest.raises(RuntimeError):
        async with p.record_run(sid):
            raise RuntimeError("boom")

    assert isinstance(p.last_snapshot, NodeSnapshot)
    assert p.last_snapshot.status == "error"
    assert p.last_snapshot.duration is not None


@pytest.mark.asyncio
async def test_full_state_persistence_deep_copy_and_history():
    p = FullStatePersistence(deep_copy=True)

    # deep copy on node snapshot
    s = {"a": [1]}
    await p.snapshot_node(state=s, next_node=DummyNode)
    assert isinstance(p.history, list)
    assert isinstance(p.history[-1], NodeSnapshot)
    assert p.history[-1].state == {"a": [1]}
    s["a"].append(2)
    # snapshot should not change after mutation
    assert p.history[-1].state == {"a": [1]}

    # load next to pending
    snap = await p.load_next()
    assert isinstance(snap, NodeSnapshot)
    assert snap.status == "pending"

    sid = p.peek_last_id()
    # record run success
    async with p.record_run(sid):
        pass
    # last history entry is still the node snapshot (status success)
    assert isinstance(p.history[-1], NodeSnapshot)
    assert p.history[-1].status == "success"

    # deep copy on end snapshot
    result = {"ok": True, "arr": [1, 2]}
    await p.snapshot_end(state={"b": 1}, result=result)
    assert isinstance(p.history[-1], EndSnapshot)
    result["arr"].append(3)
    assert p.history[-1].result == {"ok": True, "arr": [1, 2]}

    # JSON round-trip excludes node object but keeps node_name
    data = p.dump_json()
    p2 = FullStatePersistence()
    p2.load_json(data)
    assert len(p2.history) == len(p.history)
    node_snaps = [s for s in p2.history if isinstance(s, NodeSnapshot)]
    assert node_snaps
    assert all(ns.node is None for ns in node_snaps)
    assert any(ns.node_name == "dummy_node" for ns in node_snaps)

    # rebind node objects by name
    p2.rebind_nodes({"dummy_node": DummyNode})
    assert any(ns.node is DummyNode for ns in node_snaps)


@pytest.mark.asyncio
async def test_full_state_persistence_idempotent_and_errors():
    p = FullStatePersistence()
    await p.snapshot_node(state={}, next_node=DummyNode)
    assert isinstance(p.history, list)
    first_id = p.history[-1].id
    # same id -> no new snapshot
    await p.snapshot_node_if_new(first_id, state={"x": 1}, next_node=DummyNode)
    assert len(p.history) == 1
    # new id -> add
    await p.snapshot_node_if_new("some-other-id", state={}, next_node=DummyNode)
    assert len(p.history) == 2

    # record_run with unknown id
    with pytest.raises(LookupError):
        async with p.record_run("missing-id"):
            pass

    # record_run with invalid status
    # mark first to success
    await p.load_next()
    async with p.record_run(first_id):
        pass
    # calling again must fail because status is now 'success'
    with pytest.raises(ValueError):
        async with p.record_run(first_id):
            pass
