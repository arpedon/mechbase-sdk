// Example: start a route execution, add an ad-hoc field item, and complete the
// execution. Run with MECHBASE_TOKEN, MECHBASE_URL, and ROUTE_UUID set.
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
	routeUUID := os.Getenv("ROUTE_UUID")
	if token == "" || baseURL == "" || routeUUID == "" {
		log.Fatal("MECHBASE_TOKEN, MECHBASE_URL and ROUTE_UUID must be set")
	}

	ctx := context.Background()
	client := mechbase.New(token, baseURL)

	me, err := client.Me(ctx)
	if err != nil {
		log.Fatalf("me: %v", err)
	}
	inst := client.ForInstallation(me.CurrentInstallationID)

	exec, err := inst.Routes.Start(ctx, routeUUID)
	if err != nil {
		log.Fatalf("start: %v", err)
	}
	fmt.Printf("started execution %s\n", exec.UUID)

	if _, err := exec.AddFieldItem(ctx, mechbase.FieldItemInput{
		Label:    "Stray oil leak near pump 3",
		ItemType: "observation",
		Notes:    "spotted during walkdown",
	}); err != nil {
		log.Fatalf("add field item: %v", err)
	}

	done, err := exec.Complete(ctx)
	if err != nil {
		log.Fatalf("complete: %v", err)
	}
	fmt.Printf("execution %s status=%s\n", done.UUID, done.Status)
}
