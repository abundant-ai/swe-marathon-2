#pragma once

#include "CoreMinimal.h"

class UStaticMeshComponent;
class UWorld;

namespace BRWorld
{
    void BuildScenery(UWorld& World);
    void SpawnInteractives(UWorld& World);
    FTransform PlayerSpawn(int32 Slot);
    void TintMesh(UStaticMeshComponent& Component, const FLinearColor& Color);
}
