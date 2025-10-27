import unittest
from unittest.mock import MagicMock, patch
from neural_engine.tools.strava_get_my_activities_tool import StravaGetMyActivitiesTool
from neural_engine.tools.strava_get_dashboard_feed_tool import StravaGetDashboardFeedTool
from neural_engine.tools.strava_update_activity_tool import StravaUpdateActivityTool
from neural_engine.tools.strava_get_activity_kudos_tool import StravaGetActivityKudosTool
from neural_engine.tools.strava_give_kudos_tool import StravaGiveKudosTool

class TestStravaTools(unittest.TestCase):
    @patch("neural_engine.tools.strava_get_my_activities_tool.KeyValueStore")
    @patch("neural_engine.tools.strava_get_my_activities_tool.StravaClient")
    def test_get_my_activities_tool(self, mock_strava_client, mock_kv_store):
        mock_client_instance = mock_strava_client.return_value
        mock_client_instance.get_logged_in_athlete_activities.return_value = [{"id": 1, "name": "Morning Run"}]

        tool = StravaGetMyActivitiesTool()
        result = tool.execute()

        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["items"][0]["name"], "Morning Run")
        mock_strava_client.assert_called_once()
        mock_client_instance.get_logged_in_athlete_activities.assert_called_once()

    @patch("neural_engine.tools.strava_get_dashboard_feed_tool.KeyValueStore")
    @patch("neural_engine.tools.strava_get_dashboard_feed_tool.StravaClient")
    def test_get_dashboard_feed_tool(self, mock_strava_client, mock_kv_store):
        mock_client_instance = mock_strava_client.return_value
        mock_client_instance.get_dashboard_feed.return_value = {"entries": [{"entity": "Activity", "activity": {"id": 1, "startDate": "2025-10-27T00:00:00Z", "athlete": {}, "kudosAndComments": {}}}]}

        tool = StravaGetDashboardFeedTool()
        result = tool.execute()

        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 1)
        mock_strava_client.assert_called_once()
        mock_client_instance.get_dashboard_feed.assert_called_once()

    @patch("neural_engine.tools.strava_update_activity_tool.KeyValueStore")
    @patch("neural_engine.tools.strava_update_activity_tool.StravaClient")
    def test_update_activity_tool(self, mock_strava_client, mock_kv_store):
        mock_client_instance = mock_strava_client.return_value
        mock_client_instance.update_activity.return_value = {"success": True}

        tool = StravaUpdateActivityTool()
        result = tool.execute(activity_id=1, name="New Name")

        self.assertTrue(result["success"])
        mock_strava_client.assert_called_once()
        mock_client_instance.update_activity.assert_called_once_with(activity_id=1, name="New Name", description=None, visibility=None, map_visibility=None, selected_polyline_style=None)

    @patch("neural_engine.tools.strava_get_activity_kudos_tool.KeyValueStore")
    @patch("neural_engine.tools.strava_get_activity_kudos_tool.StravaClient")
    def test_get_activity_kudos_tool(self, mock_strava_client, mock_kv_store):
        mock_client_instance = mock_strava_client.return_value
        mock_client_instance.get_activity_kudos.return_value = [{"id": 1, "firstname": "John", "lastname": "Doe"}]

        tool = StravaGetActivityKudosTool()
        result = tool.execute(activity_id=1)

        self.assertTrue(result["success"])
        self.assertEqual(result["kudos_count"], 1)
        mock_strava_client.assert_called_once()
        mock_client_instance.get_activity_kudos.assert_called_once_with(1)

    @patch("neural_engine.tools.strava_give_kudos_tool.KeyValueStore")
    @patch("neural_engine.tools.strava_give_kudos_tool.StravaClient")
    def test_give_kudos_tool(self, mock_strava_client, mock_kv_store):
        mock_client_instance = mock_strava_client.return_value
        mock_client_instance.give_kudos.return_value = True

        tool = StravaGiveKudosTool()
        result = tool.execute(activity_id=1)

        self.assertTrue(result["success"])
        mock_strava_client.assert_called_once()
        mock_client_instance.give_kudos.assert_called_once_with(1)

if __name__ == "__main__":
    unittest.main()
