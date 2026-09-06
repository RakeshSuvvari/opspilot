package kubernetes

import (
	"context"
	"fmt"
	"sort"
	"strings"

	corev1 "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/fields"
)

func (c *Client) GetEvents(ctx context.Context, namespace, objectName, objectKind string, limit int) ([]EventSummary, error) {
	selector := fields.Set{}
	if objectName != "" {
		selector["involvedObject.name"] = objectName
	}
	if objectKind != "" {
		selector["involvedObject.kind"] = objectKind
	}

	events, err := c.clientset.CoreV1().Events(namespace).List(ctx, metav1.ListOptions{FieldSelector: selector.AsSelector().String()})
	if err != nil {
		return nil, fmt.Errorf("list events in namespace %q: %w", namespace, err)
	}

	result := make([]EventSummary, 0, len(events.Items))
	for i := range events.Items {
		event := &events.Items[i]
		first, last := eventTimestamps(event)
		source := event.Source.Component
		if event.ReportingController != "" {
			source = event.ReportingController
		}
		result = append(result, EventSummary{
			Namespace:      event.Namespace,
			Type:           event.Type,
			Reason:         event.Reason,
			Message:        strings.TrimSpace(event.Message),
			Count:          event.Count,
			Source:         source,
			ObjectKind:     event.InvolvedObject.Kind,
			ObjectName:     event.InvolvedObject.Name,
			FirstTimestamp: first,
			LastTimestamp:  last,
		})
	}

	sort.SliceStable(result, func(i, j int) bool {
		return result[i].LastTimestamp > result[j].LastTimestamp
	})

	if limit <= 0 {
		limit = 50
	}
	if limit > 200 {
		limit = 200
	}
	if len(result) > limit {
		result = result[:limit]
	}
	return result, nil
}

func eventTimestamps(event *corev1.Event) (string, string) {
	first := timestamp(event.FirstTimestamp)
	last := timestamp(event.LastTimestamp)

	if first == "" {
		first = timestamp(event.CreationTimestamp)
	}
	if last == "" && !event.EventTime.IsZero() {
		last = event.EventTime.Time.UTC().Format(timeFormat)
	}
	if last == "" {
		last = first
	}
	return first, last
}
