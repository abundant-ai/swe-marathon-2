#pragma once

#include "GameFramework/HUD.h"
#include "BRHUD.generated.h"

UCLASS()
class BATTLEROYALE_API ABRHUD : public AHUD
{
    GENERATED_BODY()

public:
    virtual void DrawHUD() override;
};
