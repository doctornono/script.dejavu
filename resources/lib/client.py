# -*- coding: utf-8 -*-
import xbmc
import xbmcgui
import json
import time

class DejaVuClient:
    """
    Client for interacting with script.dejavu via RPC (Kodi Notifications).
    This allows other addons to query watchlist, history, lists, etc., 
    without having to manage API keys or direct network calls.
    """
    
    def __init__(self, timeout=5):
        """
        :param timeout: Maximum time in seconds to wait for a response.
        """
        self.timeout = timeout
        self.window = xbmcgui.Window(10000)

    def _log(self, msg, level=xbmc.LOGDEBUG):
        xbmc.log(f"[script.dejavu.Client] {msg}", level)

    def call(self, action, params=None):
        """
        Sends an RPC request to script.dejavu and waits for the result.
        
        :param action: The action name (e.g., 'get_watchlist', 'get_up_next')
        :param params: Dictionary of parameters for the action.
        :return: The result (dict/list) or None if error/timeout.
        """
        method = f"script.dejavu.{action}"
        result_property = f"{method}.result"
        
        # 1. Clear previous result to ensure we don't read stale data
        self.window.clearProperty(result_property)
        
        # 2. Prepare payload
        data = params if params else {}
        # We can specify where we want the result, defaults to script.dejavu.<ACTION>.result
        data["result_property"] = result_property
        
        # 3. Send Notification
        # The sender can be anything, but let's be descriptive
        sender = xbmc.getAddonInfo('id')
        payload = json.dumps(data)
        
        self._log(f"Calling {method} with {payload}")
        xbmc.executebuiltin(f'NotifyAll({sender}, {method}, {payload})')
        
        # 4. Wait for result (Polling)
        start_time = time.time()
        while time.time() - start_time < self.timeout:
            if xbmc.Monitor().waitForAbort(0.1): # Check if Kodi is shutting down
                return None
                
            result_raw = self.window.getProperty(result_property)
            if result_raw:
                try:
                    result = json.loads(result_raw)
                    self._log(f"Received result for {action}")
                    return result
                except Exception as e:
                    self._log(f"Failed to parse result for {action}: {e}", xbmc.LOGERROR)
                    return None
            
        self._log(f"Timeout waiting for {action} result", xbmc.LOGWARNING)
        return None

    # --- Sugar methods for common actions ---

    def get_watchlist(self, media_type=None, page=1, page_size=20, sort="addedAt:desc"):
        """Returns the user's watchlist."""
        return self.call("get_watchlist", {
            "type": media_type,
            "page": page,
            "page_size": page_size,
            "sort": sort
        })

    def get_lists(self, page=1, page_size=20):
        """Returns the user's custom lists."""
        return self.call("get_lists", {
            "page": page,
            "page_size": page_size
        })

    def get_up_next(self, page=1, page_size=20):
        """Returns the 'Up Next' episodes."""
        return self.call("get_up_next", {
            "page": page,
            "page_size": page_size
        })

    def get_history(self, media_type=None, page=1, page_size=20):
        """Returns playback history."""
        return self.call("get_history", {
            "type": media_type,
            "page": page,
            "page_size": page_size
        })

    def get_dashboard(self):
        """Returns the user's dashboard layout configuration.
        
        Response contains a list of widgets with their types, titles,
        and ready-to-use apiUrl values (excluding non-video widgets like 'stats').
        """
        return self.call("get_dashboard", {})

    def get_dashboard_widget(self, widget_type, list_id=None, page=1, page_size=20, minimal=False):
        """Returns the content of a specific dashboard widget.
        
        widget_type : "up_next" | "recent_watchlist" | "continue_watching" |
                      "active_movie_scrobbles" | "active_tv_scrobbles" |
                      "upcoming_releases" | "upcoming_schedule" | "list"
        list_id     : required when widget_type == "list"
        """
        params = {
            "widget_type": widget_type,
            "page": page,
            "page_size": page_size,
            "minimal": minimal,
        }
        if list_id:
            params["list_id"] = list_id
        return self.call("get_dashboard_widget", params)
