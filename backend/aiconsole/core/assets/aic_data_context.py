import asyncio
import logging
from collections import defaultdict, deque
from typing import Any, Callable, Deque, Tuple, Type, cast, overload

from aiconsole.api.websockets.connection_manager import (
    AICConnection,
    connection_manager,
)
from aiconsole.api.websockets.server_messages import (
    NotifyAboutAssetMutationServerMessage,
)
from aiconsole.core.assets.agents.agent import AICAgent
from aiconsole.core.assets.materials.material import AICMaterial
from aiconsole.core.assets.users.users import AICUserProfile
from aiconsole.core.chat.root import Root
from aiconsole.core.chat.types import AICChat, AICMessage, AICMessageGroup, AICToolCall
from aiconsole.core.project.project import get_project_assets
from fastmutation.apply_mutation import apply_mutation
from fastmutation.data_context import DataContext
from fastmutation.mutations import AssetMutation
from fastmutation.types import AnyRef, BaseObject, CollectionRef, ObjectRef

_log = logging.getLogger(__name__)


def create_set_event() -> asyncio.Event:
    e = asyncio.Event()
    e.set()
    return e


_acquired_locks: dict[ObjectRef, asyncio.Event] = defaultdict(create_set_event)
_lock = asyncio.Lock()


def _find_object(root: BaseObject, obj: ObjectRef) -> BaseObject | None:
    base_collection = _find_collection(root, obj.parent_collection)

    if not base_collection:
        raise ValueError(f"Collection {obj.parent_collection} not found")

    if obj.id not in base_collection:
        raise ValueError(f"Object {obj.id} not found")

    return next((item for item in base_collection if item.id == obj.id), None)


def _find_collection(root: BaseObject, collection: CollectionRef):
    base_object: BaseObject | None = root

    if collection.parent:
        base_object = _find_object(root, collection.parent)

    return cast(list[Any], getattr(base_object, collection.id, None))


async def _wait_for_lock(ref: ObjectRef, lock_timeout=30) -> None:
    try:
        _log.debug(f"Waiting for lock {ref}")
        await asyncio.wait_for(_acquired_locks[ref].wait(), timeout=lock_timeout)
    except asyncio.TimeoutError:
        raise Exception(f"Lock acquisition timed out for {ref}")


class AssetOperationManager:
    def __init__(self):
        self.operations: Deque[Tuple[Callable, Tuple[Any, ...]]] = deque()

    def queue_operation(self, operation: Callable, *args):
        self.operations.append((operation, args))

    async def execute_operations(self):
        while self.operations:
            operation, args = self.operations.popleft()
            await operation(*args)


class AICFileDataContext(DataContext):
    def __init__(self, origin: AICConnection | None, lock_id: str):
        self.lock_id = lock_id
        self.origin = origin
        self.asset_operation_manager = AssetOperationManager()

    async def mutate(self, mutation: "AssetMutation", originating_from_server: bool) -> None:
        async with _lock:
            try:
                await apply_mutation(self, mutation)
                if mutation.ref not in _acquired_locks or (
                    mutation.ref not in _acquired_locks and _acquired_locks[mutation.ref].is_set()
                ):
                    await self.asset_operation_manager.execute_operations()
            except Exception as e:
                _log.exception(f"Error during mutation: {e}")
                raise e

            await connection_manager().send_to_ref(
                NotifyAboutAssetMutationServerMessage(
                    request_id=self.lock_id,
                    mutation=mutation,
                ),
                mutation.ref,
                except_connection=None if originating_from_server else self.origin,
            )

        # HANDLE DELETE

        # Remove message group if it's empty
        # if not message_location.message_group.messages:
        #     chat.message_groups = [group for group in chat.message_groups if group.id != message_location.message_group.id]

        # Remove message if it's empty
        # if not tool_call.message.tool_calls and not tool_call.message.content:
        #     tool_call.message_group.messages = [
        #         m for m in tool_call.message_group.messages if m.id != tool_call.message.id
        #     ]

        # Remove message group if it's empty
        # if not tool_call.message_group.messages:
        #    chat.message_groups = [group for group in chat.message_groups if group.id != tool_call.message_group.id]

        # SET VSALUE
        # TODO: check if the role is used
        # _handle_SetMessageGroupAgentIdMutation
        # if mutation.actor_id == "user":
        #     message_group.role = "user"
        # else:
        #    message_group.role = "assistant"

    async def acquire_lock(self, ref: ObjectRef):
        _log.debug(f"[Lock] Acquiring {ref} {self.lock_id}")

        if ref in _acquired_locks:
            await _wait_for_lock(ref)

        _acquired_locks[ref].clear()

        if self.origin:
            self.origin.lock_acquired(ref=ref, request_id=self.lock_id)

    async def release_lock(self, ref: ObjectRef):
        _log.debug(f"[Lock] Releasing {ref} {self.lock_id}")

        async with _lock:
            obj = await self.get(ref)
            if obj and ref in _acquired_locks:
                _acquired_locks[ref].set()
                del _acquired_locks[ref]

                if self.origin:
                    self.origin.lock_released(ref=ref, request_id=self.lock_id)

                await self.asset_operation_manager.execute_operations()
            else:
                raise Exception(f"Lock {ref} is not acquired by {self.lock_id}")

    @overload
    async def get(self, ref: ObjectRef) -> "BaseObject | None":  # fmt: off
        ...

    @overload
    async def get(self, ref: CollectionRef) -> "list[BaseObject] | None":  # fmt: off
        ...

    async def get(self, ref: "AnyRef") -> "BaseObject | list[BaseObject] | None":
        obj: BaseObject | None = Root(id="root", assets=[])

        segments = ref.ref_segments

        if not segments:
            return obj

        segment = segments.pop(0)
        if segment == "assets":
            if not segments:
                return cast(list[BaseObject], get_project_assets().unified_assets)
            # Get the object from the assets collection
            segment = segments.pop(0)
            obj = get_project_assets().get_asset(segment)

            if obj is None or not segments:
                return obj

            while True:
                # Get the sub collection
                segment = segments.pop(0)
                col = cast(list[BaseObject], getattr(obj, segment))

                if col is None or not segments:
                    return col

                # Get the object from the sub collection
                segment = segments.pop(0)
                obj = next((x for x in col if x.id == segment), None)

                if obj is None or not segments:
                    return obj
        else:
            raise Exception(f"Unknown ref type {ref}")

    async def exists(self, ref: "AnyRef") -> bool:
        return await self.get(ref) is not None

    @property
    def type_to_cls_mapping(self) -> dict[str, Type[BaseObject]]:
        return {
            "AICMessageGroup": AICMessageGroup,
            "AICMessage": AICMessage,
            "AICToolCall": AICToolCall,
            "AICChat": AICChat,
            "AICMaterial": AICMaterial,
            "AICAgent": AICAgent,
            "AICUserProfile": AICUserProfile,
        }
