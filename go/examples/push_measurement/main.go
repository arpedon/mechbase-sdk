// Example: list the first vibration point in the current installation and push
// a fake reading. Run with MECHBASE_TOKEN and MECHBASE_URL set.
package main

import (
	"context"
	"fmt"
	"log"
	"os"

	"github.com/arpedon/mechbase-sdk/go/pkg/mechbase"
)

func main() {
	token := os.Getenv("MECHBASE_TOKEN")
	baseURL := os.Getenv("MECHBASE_URL")
	if token == "" || baseURL == "" {
		log.Fatal("MECHBASE_TOKEN and MECHBASE_URL must be set")
	}

	ctx := context.Background()
	client := mechbase.New(token, baseURL)

	me, err := client.Me(ctx)
	if err != nil {
		log.Fatalf("me: %v", err)
	}
	inst := client.ForInstallation(me.CurrentInstallationID)

	points, err := inst.MeasurementPoints.List(ctx, mechbase.ListMeasurementPointsOptions{
		TransducerType: "VB",
		Limit:          1,
	})
	if err != nil {
		log.Fatalf("list points: %v", err)
	}
	if len(points) == 0 {
		log.Fatal("no VB points")
	}
	p := points[0]
	if p.PointID == nil {
		log.Fatal("point has no numeric id")
	}

	m, err := inst.Measurements.Create(ctx, mechbase.CreateMeasurementInput{
		PointID: *p.PointID,
		Data:    map[string]any{"rms": 2.3, "peak": 5.1},
		Notes:   "pushed from go example",
	})
	if err != nil {
		log.Fatalf("create: %v", err)
	}
	fmt.Printf("created measurement %s (seq=%d)\n", m.UUID, m.PointSequence)
}
