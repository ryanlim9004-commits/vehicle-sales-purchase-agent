"""Validated session facts and bounded current-turn patches; no learned memory."""
# Learning guide:
# Keep typed session memory, allowed update paths and resource limits.
# Memory is application state; it does not train or change the model weights.
# Patches update only supported facts; task switching prevents stale quote reuse.
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from buyer_profile import BuyerProfileFrame
from seller_profile import SellerVehicleFrame
from consultation_frames import NegotiationFrame, TradeInFrame

Goal = Literal['buy', 'sell', 'negotiate', 'trade_in']


# Shared strict base for session/protocol models; extra model-invented fields are rejected.
class StrictFrame(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, allow_inf_nan=False)


# One proposed fact change needs an allowed path, a typed value, a current-message quote and an
# operation.
class SlotUpdate(StrictFrame):
    slot: str = Field(min_length=1, max_length=120)
    value: str | float | int | bool | list[str] | None
    evidence: str = Field(min_length=1, max_length=1200)
    operation: Literal['set', 'add', 'remove'] = 'set'


# A turn proposes a goal plus new updates; omitted slots are not instructions to erase existing
# memory.
class TurnPatch(StrictFrame):
    goal: Goal | None = None
    goal_evidence: str = ''
    updates: list[SlotUpdate] = Field(default_factory=list, max_length=40)


# Centralize finite input/request/turn/tool/retry budgets so a failing consultation cannot loop
# indefinitely.
class AgentLimits(StrictFrame):
    request_timeout_seconds: float = Field(default=90.0, gt=0, le=120)
    turn_timeout_seconds: float = Field(default=240.0, gt=0, le=600)
    model_retries: int = Field(default=1, ge=0, le=2)
    maximum_tool_calls: int = Field(default=10, ge=1, le=20)
    maximum_tool_errors: int = Field(default=2, ge=1, le=4)
    maximum_input_characters: int = Field(default=6000, ge=100, le=12000)


# Store confirmed per-goal Frames, provenance, unresolved issues, candidate IDs and a bounded
# event trace.
class SessionState(StrictFrame):
    schema_version: Literal[1] = 1
    goal: Goal | None = None
    buyer: BuyerProfileFrame = Field(default_factory=BuyerProfileFrame)
    seller: SellerVehicleFrame = Field(default_factory=SellerVehicleFrame)
    negotiation: NegotiationFrame = Field(default_factory=NegotiationFrame)
    trade_in: TradeInFrame = Field(default_factory=TradeInFrame)
    revision: int = Field(default=0, ge=0)
    turn: int = Field(default=0, ge=0)
    provenance: dict[str, dict] = Field(default_factory=dict)
    # provenance links accepted facts to source quotes; issues block action
    # until clarified. These serve different roles from the readable event trace.
    issues: dict[str, str] = Field(default_factory=dict)
    selected_vehicle_id: str | None = None
    negotiation_from_seller: bool = False
    trade_in_from_seller: bool = False
    ranked_vehicle_ids: list[str] = Field(default_factory=list)
    pending_slots: list[str] = Field(default_factory=list)
    trace: list[dict] = Field(default_factory=list)

    # Tag an event with its turn and retain only the latest 400 events to bound saved memory.
    def event(self, category, **details):
        self.trace.append({'turn': self.turn, 'category': category, **details})
        self.trace = self.trace[-400:]


# Derive writable leaf paths from known Frames, excluding internal notes and fixed currency fields.
def allowed_slots():
    slots = {}
    excluded = {'clarification_notes', 'input_validation_notes', 'currency'}
    for prefix, frame in [('buyer', BuyerProfileFrame()), ('seller', SellerVehicleFrame()),
                          ('negotiation', NegotiationFrame()), ('trade_in', TradeInFrame())]:
        # Visit nested Frames recursively and register only their editable leaf slots.
        def walk(value, path):
            for name, child in value.model_dump().items():
                if name in excluded:
                    continue
                nested = getattr(value, name)
                slot = path + '.' + name
                if isinstance(nested, BaseModel):
                    walk(nested, slot)
                else:
                    slots[slot] = nested
        walk(frame, prefix)
    return slots


SLOTS = allowed_slots()


# Apply a set/add/remove to a copied frame dictionary, then validate the entire frame before
# replacing memory.
def set_slot(state, path, value, operation='set'):
    root, *keys = path.split('.')
    # Paths such as trade_in.trade_in_quote.fees_myr address known nested
    # dictionaries; the caller has already checked membership in SLOTS.
    frame = getattr(state, root)
    data = frame.model_dump()
    target = data
    for name in keys[:-1]:
        target = target[name]
    name = keys[-1]
    previous = target[name]
    if operation in ('add', 'remove'):
        if not isinstance(previous, list) or not isinstance(value, list):
            raise ValueError('Add/remove operations are only supported for list facts.')
        if operation == 'add':
            value = list(dict.fromkeys(previous + value))
        else:
            removed = {v.casefold().strip() for v in value}
            value = [v for v in previous if v.casefold().strip() not in removed]
    target[name] = value
    # Validate a replacement Frame rather than mutating one field in place.
    # If validation fails, the new object is never installed as confirmed state.
    setattr(state, root, type(frame).model_validate(data))


# Reset destination-task amounts and selectively carry confirmed vehicle identity, preserving
# damage handoff flags.
def switch_goal(state, goal):
    if goal == state.goal:
        return
    previous = state.goal
    selected_identity = state.negotiation.vehicle.model_dump() if previous == 'buy' and state.selected_vehicle_id else None
    # Starting a different task clears the destination profile, preventing
    # unrelated stale amounts from becoming a new customer's requirements.
    mapping = {'buy': ('buyer', BuyerProfileFrame), 'sell': ('seller', SellerVehicleFrame),
               'negotiate': ('negotiation', NegotiationFrame), 'trade_in': ('trade_in', TradeInFrame)}
    attr, frame = mapping[goal]
    setattr(state, attr, frame())
    state.issues = {}
    state.pending_slots = []
    state.negotiation_from_seller = False
    state.trade_in_from_seller = False
    if goal == 'negotiate' and previous == 'sell':
        # Reuse identity only. The from_seller flag tells later tools to carry
        # reported damage history; it does not authorize reuse of old cash quotes.
        identity = {k: getattr(state.seller, k) for k in ('brand', 'model', 'variant', 'year', 'transmission')}
        state.negotiation = NegotiationFrame.model_validate({'vehicle': identity})
        state.negotiation_from_seller = True
        state.event('facts', action='reuse_vehicle_identity', source='previous confirmed seller facts', values=identity)
    if goal == 'negotiate' and selected_identity is not None:
        state.negotiation = NegotiationFrame.model_validate({'vehicle': selected_identity})
        state.event('facts', action='reuse_vehicle_identity', source='previous verified buyer selection', values=selected_identity)
    if goal == 'trade_in' and previous == 'sell':
        identity = {k: getattr(state.seller, k) for k in ('brand', 'model', 'variant', 'year', 'transmission')}
        state.trade_in = TradeInFrame.model_validate({'current_vehicle': identity})
        state.trade_in_from_seller = True
        state.event('facts', action='reuse_vehicle_identity', source='previous confirmed seller facts', values=identity)
    if goal in ('buy', 'sell', 'trade_in'):
        state.selected_vehicle_id = None
        state.ranked_vehicle_ids = []
    state.goal = goal
    state.event('facts', action='switch_goal', previous=previous, goal=goal)
