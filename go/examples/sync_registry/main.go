// Example: upsert a section/zone/asset/point chain by external_id, then batch-push
// a reading. Mirrors python/examples/sync_registry.py.
//
// Set MECHBASE_TOKEN before running; base URL defaults to https://app.mechbase.io.
package main

import (
	"context"
	"fmt"
	"log"
	"os"

	"github.com/arpedon/mechbase-sdk/go/pkg/mechbase"
)

func ptr[T any](v T) *T { return &v }

func main() {
	token := os.Getenv("MECHBASE_TOKEN")
	if token == "" {
		token = "..."
	}

	ctx := context.Background()
	client := mechbase.New(token, "")

	me, err := client.Me(ctx)
	if err != nil {
		log.Fatalf("me: %v", err)
	}
	inst := client.ForInstallation(me.CurrentInstallationID)

	// Upsert the hierarchy by external_id — safe to run repeatedly.
	if _, err := inst.Sections.Upsert(ctx, mechbase.SectionInput{
		ExternalID: ptr("HALL-A"),
		Name:       ptr("Hall A"),
	}); err != nil {
		log.Fatalf("sections.upsert: %v", err)
	}

	if _, err := inst.Zones.Upsert(ctx, mechbase.ZoneInput{
		ExternalID:        ptr("Z-1"),
		Name:              ptr("Pump Row"),
		SectionExternalID: ptr("HALL-A"),
	}); err != nil {
		log.Fatalf("zones.upsert: %v", err)
	}

	if _, err := inst.Assets.Upsert(ctx, mechbase.AssetInput{
		ExternalID:     ptr("PUMP-1"),
		Name:           ptr("Feed Pump 1"),
		ZoneExternalID: ptr("Z-1"),
		EquipmentType:  ptr("pump"),
		MachineClass:   ptr("II"),
	}); err != nil {
		log.Fatalf("assets.upsert: %v", err)
	}

	if _, err := inst.MeasurementPoints.Upsert(ctx, mechbase.PointInput{
		ExternalID:          ptr("PUMP-1-DE"),
		Name:                ptr("Drive End"),
		AssetExternalID:     ptr("PUMP-1"),
		TransducerType:      ptr("accel"),
		MeasurementUnitCode: ptr("mm_s"),
	}); err != nil {
		log.Fatalf("measurement_points.upsert: %v", err)
	}

	// Push readings in bulk.
	result, err := inst.Measurements.CreateBatch(ctx, []mechbase.MeasurementInput{
		{
			MeasurementPointExternalID: ptr("PUMP-1-DE"),
			Data:                       map[string]any{"rms": 2.3},
			ExternalID:                 ptr("r-1"),
		},
	})
	if err != nil {
		log.Fatalf("measurements.create_batch: %v", err)
	}
	fmt.Printf("created=%d duplicates=%d errors=%d\n",
		result.Created, result.Duplicates, result.Errors)
}
