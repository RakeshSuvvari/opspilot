import unittest

from opspilot_agent.observability import extract_tool_records, ordered_unique_tool_names


class _Call:
    type = "tool_call_item"

    def __init__(self):
        self.tool_name = "k8s_get_pod"
        self.call_id = "call-1"
        self.raw_item = {"arguments": '{"namespace":"opspilot-demo","pod_name":"payment-1"}'}


class _Output:
    type = "tool_call_output_item"

    def __init__(self):
        self.call_id = "call-1"
        self.output = '{"name":"payment-1","phase":"Running"}'


class ObservabilityTests(unittest.TestCase):
    def test_ordered_unique_tool_names(self):
        class Record:
            def __init__(self, name):
                self.name = name

        names = ordered_unique_tool_names(
            [Record("k8s_list_pods"), Record("k8s_get_pod"), Record("k8s_list_pods")]
        )
        self.assertEqual(names, ["k8s_list_pods", "k8s_get_pod"])

    def test_extract_tool_records_pairs_call_and_structured_output(self):
        records = extract_tool_records([_Call(), _Output()])
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].name, "k8s_get_pod")
        self.assertEqual(records[0].arguments["pod_name"], "payment-1")
        self.assertEqual(records[0].output["phase"], "Running")


if __name__ == "__main__":
    unittest.main()
