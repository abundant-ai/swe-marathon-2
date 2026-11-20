#pragma once

#include "CoreMinimal.h"
#include "BRTypes.generated.h"

UENUM()
enum class EBRMatchPhase : uint8
{
    Waiting,
    Playing,
    Finished
};

UENUM()
enum class EBRRifle : uint8
{
    None,
    AK47,
    M16
};

UENUM()
enum class EBRItem : uint8
{
    AK47,
    M16,
    AKAmmo,
    M16Ammo
};
