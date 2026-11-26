# Power plan

`import Yasb`

Windows' power plans and the active one, with a function to switch plans. Read again when Windows' power plans
key in the registry changes.

PowerPlans is a singleton: use it by its name, without creating it.

## PowerPlans

### Properties

#### plans : list `read-only`

The power plans, in the order Windows lists them. Each is an object:

- `id` : string, the plan's GUID, in upper case without braces.
- `name` : string, the plan's name. Its `id` when it has none.

#### activeId : string `read-only`

`id` of the active plan. `""` until the first reading.

#### loading : bool `read-only`

`true` while the plans are read or a plan is switched.

#### error : string `read-only`

Last error, `""` when none. Cleared when the next read or switch starts.

- `Windows did not activate the selected power plan.`: Windows kept another plan.
- `Could not change the power plan.`, sometimes followed by Windows' reason: the switch failed.
- `Could not read Windows power plans.` or `Windows did not return an active power plan.`: reading failed.

### Functions

#### refresh()

Reads the plans again. While `loading`, reads once more after the current reading.

#### selectPlan(planId: string)

Makes the plan with this `id` the active one. Ignored when it is already active or not in `plans`. While
`loading`, the plan chosen last is switched to once the reading is done.

PowerPlans has no signals.

## Used by

YASB's own Power plan widget, listed in [Widgets](./Widgets).
