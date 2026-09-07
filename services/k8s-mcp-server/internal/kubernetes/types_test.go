package kubernetes

import (
	"encoding/json"
	"testing"
)

func TestPodDetailsContainerFieldsUseDistinctGoNames(t *testing.T) {
	pod := PodDetails{
		PodSummary: PodSummary{
			Name: "payment-abc",
			ContainerStates: []ContainerState{{
				Name:  "payment",
				State: "waiting",
			}},
		},
		Containers: []ContainerDetails{{
			ContainerState: ContainerState{
				Name:  "payment",
				State: "waiting",
			},
			Image: "opspilot/payment:dev",
		}},
	}

	payload, err := json.Marshal(pod)
	if err != nil {
		t.Fatalf("json.Marshal() error = %v", err)
	}

	var output map[string]json.RawMessage
	if err := json.Unmarshal(payload, &output); err != nil {
		t.Fatalf("json.Unmarshal() error = %v", err)
	}

	if _, ok := output["containers"]; !ok {
		t.Fatal("expected pod summary containers field")
	}
	if _, ok := output["container_details"]; !ok {
		t.Fatal("expected detailed container field")
	}
}
