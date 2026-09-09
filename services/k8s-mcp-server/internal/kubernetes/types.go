package kubernetes

type PodSummary struct {
	Name            string            `json:"name"`
	Namespace       string            `json:"namespace"`
	Phase           string            `json:"phase"`
	Ready           bool              `json:"ready"`
	Restarts        int32             `json:"restarts"`
	Node            string            `json:"node,omitempty"`
	PodIP           string            `json:"pod_ip,omitempty"`
	StartTime       string            `json:"start_time,omitempty"`
	Labels          map[string]string `json:"labels,omitempty"`
	ContainerStates []ContainerState  `json:"containers"`
}

type PodDetails struct {
	PodSummary
	Conditions []PodCondition     `json:"conditions"`
	Containers []ContainerDetails `json:"container_details"`
}

type PodCondition struct {
	Type               string `json:"type"`
	Status             string `json:"status"`
	Reason             string `json:"reason,omitempty"`
	Message            string `json:"message,omitempty"`
	LastTransitionTime string `json:"last_transition_time,omitempty"`
}

type ContainerState struct {
	Name                  string `json:"name"`
	Ready                 bool   `json:"ready"`
	RestartCount          int32  `json:"restart_count"`
	State                 string `json:"state"`
	Reason                string `json:"reason,omitempty"`
	ExitCode              int32  `json:"exit_code,omitempty"`
	StartedAt             string `json:"started_at,omitempty"`
	FinishedAt            string `json:"finished_at,omitempty"`
	LastTerminationReason string `json:"last_termination_reason,omitempty"`
	LastExitCode          int32  `json:"last_exit_code,omitempty"`
	LastFinishedAt        string `json:"last_finished_at,omitempty"`
}

type ContainerDetails struct {
	ContainerState
	Image          string            `json:"image"`
	Requests       map[string]string `json:"requests,omitempty"`
	Limits         map[string]string `json:"limits,omitempty"`
	Environment    []EnvironmentVar  `json:"environment,omitempty"`
	ReadinessProbe *ProbeDetails     `json:"readiness_probe,omitempty"`
	LivenessProbe  *ProbeDetails     `json:"liveness_probe,omitempty"`
}

type EnvironmentVar struct {
	Name      string `json:"name"`
	Value     string `json:"value,omitempty"`
	ValueFrom string `json:"value_from,omitempty"`
	Redacted  bool   `json:"redacted,omitempty"`
}

type ProbeDetails struct {
	Type             string   `json:"type"`
	Path             string   `json:"path,omitempty"`
	Port             string   `json:"port,omitempty"`
	Scheme           string   `json:"scheme,omitempty"`
	Command          []string `json:"command,omitempty"`
	InitialDelaySecs int32    `json:"initial_delay_seconds,omitempty"`
	PeriodSecs       int32    `json:"period_seconds,omitempty"`
	TimeoutSecs      int32    `json:"timeout_seconds,omitempty"`
	FailureThreshold int32    `json:"failure_threshold,omitempty"`
}

type PodLogs struct {
	Namespace string `json:"namespace"`
	Pod       string `json:"pod"`
	Container string `json:"container,omitempty"`
	Previous  bool   `json:"previous"`
	TailLines int64  `json:"tail_lines"`
	Logs      string `json:"logs"`
}

type EventSummary struct {
	Namespace      string `json:"namespace"`
	Type           string `json:"type"`
	Reason         string `json:"reason"`
	Message        string `json:"message"`
	Count          int32  `json:"count"`
	Source         string `json:"source,omitempty"`
	ObjectKind     string `json:"object_kind,omitempty"`
	ObjectName     string `json:"object_name,omitempty"`
	FirstTimestamp string `json:"first_timestamp,omitempty"`
	LastTimestamp  string `json:"last_timestamp,omitempty"`
}

type DeploymentDetails struct {
	Name                   string                `json:"name"`
	Namespace              string                `json:"namespace"`
	Generation             int64                 `json:"generation"`
	ObservedGeneration     int64                 `json:"observed_generation"`
	Replicas               int32                 `json:"replicas"`
	ReadyReplicas          int32                 `json:"ready_replicas"`
	AvailableReplicas      int32                 `json:"available_replicas"`
	UpdatedReplicas        int32                 `json:"updated_replicas"`
	Strategy               string                `json:"strategy"`
	Selector               map[string]string     `json:"selector,omitempty"`
	Annotations            map[string]string     `json:"annotations,omitempty"`
	PodTemplateLabels      map[string]string     `json:"pod_template_labels,omitempty"`
	PodTemplateAnnotations map[string]string     `json:"pod_template_annotations,omitempty"`
	Containers             []DeploymentContainer `json:"containers"`
	Conditions             []DeploymentCondition `json:"conditions,omitempty"`
}

type DeploymentContainer struct {
	Name           string            `json:"name"`
	Image          string            `json:"image"`
	Requests       map[string]string `json:"requests,omitempty"`
	Limits         map[string]string `json:"limits,omitempty"`
	Environment    []EnvironmentVar  `json:"environment,omitempty"`
	ReadinessProbe *ProbeDetails     `json:"readiness_probe,omitempty"`
	LivenessProbe  *ProbeDetails     `json:"liveness_probe,omitempty"`
}

type DeploymentCondition struct {
	Type               string `json:"type"`
	Status             string `json:"status"`
	Reason             string `json:"reason,omitempty"`
	Message            string `json:"message,omitempty"`
	LastTransitionTime string `json:"last_transition_time,omitempty"`
}

type RestartDeploymentResult struct {
	Namespace          string `json:"namespace"`
	Deployment         string `json:"deployment"`
	RestartedAt        string `json:"restarted_at"`
	PreviousGeneration int64  `json:"previous_generation"`
	Generation         int64  `json:"generation"`
}

type ScaleDeploymentResult struct {
	Namespace        string `json:"namespace"`
	Deployment       string `json:"deployment"`
	PreviousReplicas int32  `json:"previous_replicas"`
	Replicas         int32  `json:"replicas"`
	ScaledAt         string `json:"scaled_at"`
}

type RollbackDeploymentResult struct {
	Namespace          string `json:"namespace"`
	Deployment         string `json:"deployment"`
	FromRevision       int64  `json:"from_revision"`
	ToRevision         int64  `json:"to_revision"`
	TargetReplicaSet   string `json:"target_replicaset"`
	Generation         int64  `json:"generation"`
	FromSourceRevision string `json:"from_source_revision,omitempty"`
	ToSourceRevision   string `json:"to_source_revision,omitempty"`
	RolledBackAt       string `json:"rolled_back_at"`
}
