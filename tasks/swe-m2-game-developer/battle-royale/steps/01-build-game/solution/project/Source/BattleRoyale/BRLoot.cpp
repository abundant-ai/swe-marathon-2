#include "BRLoot.h"

#include "BRCharacter.h"
#include "Components/SceneComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialInterface.h"
#include "Net/UnrealNetwork.h"
#include "UObject/ConstructorHelpers.h"

ABRLoot::ABRLoot()
{
    PrimaryActorTick.bCanEverTick = false;
    bReplicates = true;
    Root = CreateDefaultSubobject<USceneComponent>(TEXT("Pickup"));
    SetRootComponent(Root);

    static ConstructorHelpers::FObjectFinder<UStaticMesh> Cube(TEXT("/Engine/BasicShapes/Cube.Cube"));
    static ConstructorHelpers::FObjectFinder<UMaterialInterface> BaseMaterial(
        TEXT("/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial"));
    const TCHAR* Names[] = {TEXT("Base"), TEXT("Accent"), TEXT("Marking"), TEXT("Handle")};
    for (const TCHAR* Name : Names)
    {
        UStaticMeshComponent* Part = CreateDefaultSubobject<UStaticMeshComponent>(Name);
        Part->SetupAttachment(Root);
        Part->SetStaticMesh(Cube.Object);
        Part->SetMaterial(0, BaseMaterial.Object);
        Part->SetCollisionEnabled(ECollisionEnabled::NoCollision);
        Part->SetGenerateOverlapEvents(false);
        Parts.Add(Part);
    }
}

void ABRLoot::BeginPlay()
{
    Super::BeginPlay();
    OnRep_Item();
}

void ABRLoot::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
    Super::GetLifetimeReplicatedProps(OutLifetimeProps);
    DOREPLIFETIME(ABRLoot, Item);
    DOREPLIFETIME(ABRLoot, Amount);
}

void ABRLoot::Configure(EBRItem InItem, int32 InAmount)
{
    if (HasAuthority() && !bCollected)
    {
        Item = InItem;
        Amount = FMath::Max(1, InAmount);
        OnRep_Item();
        ForceNetUpdate();
    }
}

bool ABRLoot::TryCollect(ABRCharacter* Player)
{
    if (!HasAuthority() || bCollected || !IsValid(Player)
        || FVector::DistSquared(Player->GetActorLocation(), GetActorLocation()) > FMath::Square(260.0)
        || !Player->TryGiveItem(Item, Amount))
    {
        return false;
    }
    bCollected = true;
    UE_LOG(LogTemp, Display, TEXT("BR pickup: %s collected item %d x%d"),
        *Player->GetName(), static_cast<int32>(Item), Amount);
    Destroy();
    return true;
}

void ABRLoot::OnRep_Item()
{
    const bool bRifle = Item == EBRItem::AK47 || Item == EBRItem::M16;
    const bool bWarm = Item == EBRItem::AK47 || Item == EBRItem::AKAmmo;
    const FLinearColor Accent = bWarm ? FLinearColor(.62f, .25f, .065f) : FLinearColor(.08f, .43f, .57f);
    const FLinearColor Dark(.07f, .09f, .08f);
    const FLinearColor Bright(.78f, .75f, .59f);
    const FLinearColor Colors[] = {Dark, Accent, Bright, Dark};
    const FVector Locations[] = {
        bRifle ? FVector(0, 0, 3) : FVector(0, 0, 0),
        bRifle ? FVector(-24, 0, 3) : FVector(0, 0, 10),
        bRifle ? FVector(27, 0, 3) : FVector(0, 0, 11),
        bRifle ? FVector(3, -6, 3) : FVector(0, 0, 13),
    };
    const FVector Scales[] = {
        bRifle ? FVector(.59, .085, .085) : FVector(.34, .25, .19),
        bRifle ? FVector(.23, .13, .095) : FVector(.34, .25, .03),
        bRifle ? FVector(.25, .045, .045) : FVector(.12, .2, .025),
        bRifle ? FVector(.12, .17, .080) : FVector(.12, .048, .035),
    };
    for (int32 Index = 0; Index < Parts.Num(); ++Index)
    {
        UStaticMeshComponent* Part = Parts[Index];
        Part->SetRelativeLocation(Locations[Index]);
        Part->SetRelativeScale3D(Scales[Index]);
        if (UMaterialInstanceDynamic* Material = Part->CreateDynamicMaterialInstance(0))
        {
            Material->SetVectorParameterValue(TEXT("Color"), Colors[Index]);
        }
    }
}
