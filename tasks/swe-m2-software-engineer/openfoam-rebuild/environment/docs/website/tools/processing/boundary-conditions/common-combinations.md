<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/common-combinations -->

# Common combinations

## Pressure\-velocity systems

### Incompressible

| Inlet | | Outlet | | Stability |
| --- | --- | --- | --- | --- |
| Physics | OpenFOAM | Physics | OpenFOAM |  |
| Volume flow rate | [flowRateInletVelocity](rtm/derived/inlet/flowRateInletVelocity.md) | Static pressure | [fixedValue](rtm/derived/general/fixedValue.md) | Excellent |
| Total pressure | [totalPressure](rtm/derived/inletOutlet/totalPressure.md) | Total pressure | [totalPressure](rtm/derived/inletOutlet/totalPressure.md) | Very good |
| Total pressure | [totalPressure](rtm/derived/inletOutlet/totalPressure.md) | Static pressure | [fixedValue](rtm/derived/general/fixedValue.md) | Good |
| Static pressure | [fixedValue](rtm/derived/general/fixedValue.md) | Static pressure | [fixedValue](rtm/derived/general/fixedValue.md) | Poor |

### Compressible

| Inlet | | Outlet | | Stability |
| --- | --- | --- | --- | --- |
| Physics | OpenFOAM | Physics | OpenFOAM |  |
| Mass flow rate | [flowRateInletVelocity](rtm/derived/inlet/flowRateInletVelocity.md) | Static pressure | [fixedValue](rtm/derived/general/fixedValue.md) | Excellent |
| Total pressure | [totalPressure](rtm/derived/inletOutlet/totalPressure.md) | Total pressure | [totalPressure](rtm/derived/inletOutlet/totalPressure.md) | Very good |
| Total pressure | [totalPressure](rtm/derived/inletOutlet/totalPressure.md) | Static pressure | [fixedValue](rtm/derived/general/fixedValue.md) | Good |
| Static pressure | [fixedValue](rtm/derived/general/fixedValue.md) | Static pressure | [fixedValue](rtm/derived/general/fixedValue.md) | Poor |

### Return flow options

| Type | Condition | Stability |
| --- | --- | --- |
| Outflow | [zeroGradient](rtm/derived/general/zeroGradient.md) | Unstable if flow reverses |
| Blocked | [inletOutlet](rtm/derived/inletOutlet/inletOutlet.md) | Good, but unphysical |
| Return flow I | [pressureInletOutlet](rtm/derived/outlet/pressureInletOutletVelocity.md) | Good |
| Return flow II | [totalPressure](rtm/derived/inletOutlet/totalPressure.md) | Very good |

## Heat transfer

### Walls

| Type | Condition |
| --- | --- |
| Adiabatic | [zeroGradient](rtm/derived/general/zeroGradient.md) |
| Fixed temperature | [fixedValue](rtm/derived/general/fixedValue.md) |
| Fixed heat flux | [fixedGradient](rtm/derived/general/fixedGradient.md) |

## Mesh motion

### Walls

| Type | Condition |
| --- | --- |
| Moving wall | [movingWallVelocity](rtm/derived/wall/movingWallVelocity.md) |
