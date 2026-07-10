#!/usr/bin/env python3
import sys
import uuid
import threading
import subprocess
import gi

gi.require_version('Gtk', '3.0')
gi.require_version('NM', '1.0')
from gi.repository import Gtk, NM, GLib, Gdk, Pango

class ConnectionDetailsDialog(Gtk.Dialog):
    def __init__(self, parent_app, device, ap, ssid, connection):
        super().__init__(title="Connection Info")
        self.set_default_size(280, 300)
        self.set_border_width(12)
        self.set_wmclass("tnywfi-dialog", "tnywfi-dialog")
        
        self.device = device
        self.ap = ap
        self.ssid = ssid
        self.connection = connection
        self.iface = device.get_iface()
        
        self.last_rx = self._get_bytes('rx')
        self.last_tx = self._get_bytes('tx')
        self.last_time = GLib.get_monotonic_time() / 1000000.0
        
        # State variables for the password toggle
        self.actual_password = None
        self.is_password_visible = False
        self.is_fetching = False
        
        vbox = self.get_content_area()
        vbox.set_spacing(15)
        
        header = Gtk.Label()
        header.set_markup(f"<span foreground='#8ab4f8' size='x-large'><b>{GLib.markup_escape_text(ssid)}</b></span>")
        vbox.pack_start(header, False, False, 0)
        
        grid = Gtk.Grid()
        grid.set_column_spacing(15)
        grid.set_row_spacing(10)
        grid.set_halign(Gtk.Align.CENTER)
        
        self.lbl_freq = Gtk.Label(xalign=0.0)
        self.lbl_bitrate = Gtk.Label(xalign=0.0)
        self.lbl_rssi = Gtk.Label(xalign=0.0)
        self.lbl_dl = Gtk.Label(xalign=0.0)
        self.lbl_ul = Gtk.Label(xalign=0.0)
        self.lbl_sec = Gtk.Label(xalign=0.0)
        
        s_wsec = self.connection.get_setting_wireless_security() if self.connection else None
        
        # --- Flat Password Button Setup ---
        self.pw_button = Gtk.Button()
        self.pw_button.set_relief(Gtk.ReliefStyle.NONE) 
        self.pw_button.set_halign(Gtk.Align.START) 
        
        if self.connection and s_wsec:
            self.pw_label = Gtk.Label(label="Click to authenticate")
            self.pw_button.connect("clicked", self.on_password_clicked)
        else:
            self.pw_label = Gtk.Label(label="None / Open")
            self.pw_button.set_sensitive(False)
            
        self.pw_label.set_xalign(0.0) 
        self.pw_button.add(self.pw_label)
        
        def add_row(grid, row, title, widget):
            lbl = Gtk.Label(label=title, xalign=1.0)
            lbl.get_style_context().add_class("dim-label")
            grid.attach(lbl, 0, row, 1, 1)
            grid.attach(widget, 1, row, 1, 1)
            
        add_row(grid, 0, "Frequency:", self.lbl_freq)
        add_row(grid, 1, "Max Bitrate:", self.lbl_bitrate)
        add_row(grid, 2, "Signal:", self.lbl_rssi)
        add_row(grid, 3, "Download:", self.lbl_dl)
        add_row(grid, 4, "Upload:", self.lbl_ul)
        add_row(grid, 5, "Security:", self.lbl_sec)
        add_row(grid, 6, "Password:", self.pw_button)
        
        vbox.pack_start(grid, True, True, 0)
        
        sec_type = "Open / None"
        if s_wsec:
            mgmt = s_wsec.get_key_mgmt()
            if mgmt == "wpa-psk": sec_type = "WPA/WPA2 Personal"
            elif mgmt == "sae": sec_type = "WPA3 Personal"
            elif mgmt == "owe": sec_type = "Enhanced Open (OWE)"
            elif mgmt == "wpa-eap": sec_type = "WPA Enterprise"
            else: sec_type = mgmt.upper()
        self.lbl_sec.set_text(sec_type)

        btn_forget = self.add_button("Forget Network", Gtk.ResponseType.REJECT)
        btn_forget.get_style_context().add_class("destructive-action")
        self.add_button("Back", Gtk.ResponseType.CLOSE)
        
        self.timeout_id = GLib.timeout_add(1000, self.update_stats)
        self.connect("response", self.on_response)
        
        self.update_stats()
        self.show_all()

    def on_password_clicked(self, button):
        if not self.connection:
            return

        if self.actual_password:
            # We already have the password, just toggle visibility
            self.is_password_visible = not self.is_password_visible
            if self.is_password_visible:
                self.pw_label.set_text(self.actual_password)
            else:
                self.pw_label.set_text("*" * len(self.actual_password))
        elif not self.is_fetching:
            # Trigger Polkit authentication in a background thread
            self.is_fetching = True
            self.pw_label.set_text("Authenticating...")
            self.pw_button.set_sensitive(False) # Prevent spam clicking
            conn_uuid = self.connection.get_uuid()
            threading.Thread(target=self._fetch_password_thread, args=(conn_uuid,), daemon=True).start()

    def _fetch_password_thread(self, conn_uuid):
        try:
            # pkexec enforces the polkit graphical prompt.
            # nmcli -s outputs secrets, -g extracts the specific password fields.
            cmd = [
                "pkexec", "nmcli", "-s", "-g", 
                "802-11-wireless-security.psk,802-11-wireless-security.wep-key0,802-1x.password", 
                "connection", "show", conn_uuid
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                lines = [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]
                if lines:
                    password = lines[0]
                    GLib.idle_add(self._on_password_fetched, password)
                else:
                    GLib.idle_add(self._on_password_fetched, "Not Found")
            else:
                # User hit cancel on the Polkit prompt, or entered the wrong password
                GLib.idle_add(self._on_password_fetched, "Auth Failed")
        except Exception as e:
            GLib.idle_add(self._on_password_fetched, "Error")

    def _on_password_fetched(self, password):
        self.is_fetching = False
        self.pw_button.set_sensitive(True)
        
        if password not in ["Not Found", "Auth Failed", "Error"]:
            self.actual_password = password
            self.is_password_visible = True
            self.pw_label.set_text(self.actual_password)
        else:
            if password == "Not Found":
                self.pw_label.set_text("No Saved Password")
                self.pw_button.set_sensitive(False)
            else:
                self.pw_label.set_text("Failed. Click to retry")
            
    def _get_bytes(self, direction):
        try:
            with open(f"/sys/class/net/{self.iface}/statistics/{direction}_bytes", "r") as f:
                return int(f.read().strip())
        except Exception:
            return 0
            
    def format_speed(self, bps):
        if bps < 1024: return f"{bps:.0f} B/s"
        elif bps < 1024**2: return f"{bps/1024:.1f} KB/s"
        else: return f"{bps/(1024**2):.2f} MB/s"
        
    def update_stats(self):
        freq = self.ap.get_frequency()
        band = f"{freq} MHz"
        if freq > 5900: band += " (6 GHz)"
        elif freq > 4000: band += " (5 GHz)"
        else: band += " (2.4 GHz)"
        
        bitrate = self.ap.get_max_bitrate() / 1000
        strength = self.ap.get_strength()
        dbm = int((strength / 2) - 100)
        
        self.lbl_freq.set_text(band)
        self.lbl_bitrate.set_text(f"{bitrate:.0f} Mbps")
        self.lbl_rssi.set_text(f"{strength}%  ({dbm} dBm)")
        
        current_time = GLib.get_monotonic_time() / 1000000.0
        dt = current_time - self.last_time
        if dt > 0:
            rx = self._get_bytes('rx')
            tx = self._get_bytes('tx')
            
            dl_speed = (rx - self.last_rx) / dt
            ul_speed = (tx - self.last_tx) / dt
            
            self.lbl_dl.set_text(self.format_speed(dl_speed))
            self.lbl_ul.set_text(self.format_speed(ul_speed))
            
            self.last_rx = rx
            self.last_tx = tx
            self.last_time = current_time
            
        return True 
        
    def on_response(self, dialog, response_id):
        if response_id == Gtk.ResponseType.REJECT:
            if self.connection:
                self.connection.delete_async(None, self.on_deleted)
        else:
            self.cleanup_and_close()
            
    def on_deleted(self, conn, res):
        try:
            conn.delete_finish(res)
        except Exception as e:
            print(f"Failed to delete: {e}")
        self.cleanup_and_close()

    def cleanup_and_close(self):
        if self.timeout_id:
            GLib.source_remove(self.timeout_id)
        self.destroy()


class WifiWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title="tnywfi")
        self.set_default_size(175, 450)
        self.set_border_width(10)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_wmclass("tnywfi", "tnywfi")

        self.client = NM.Client.new(None)
        self._apply_css()
        
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.add(vbox)

        # --- Top Status Area ---
        top_container = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        
        self.status_eventbox = Gtk.EventBox()
        self.status_eventbox.connect("button-press-event", self.on_status_clicked)
        self.status_eventbox.add_events(Gdk.EventMask.ENTER_NOTIFY_MASK | Gdk.EventMask.LEAVE_NOTIFY_MASK)
        
        def on_enter(w, e):
            window = w.get_window()
            if window: window.set_cursor(Gdk.Cursor.new_from_name(Gdk.Display.get_default(), "pointer"))
        def on_leave(w, e):
            window = w.get_window()
            if window: window.set_cursor(None)
            
        self.status_eventbox.connect("enter-notify-event", on_enter)
        self.status_eventbox.connect("leave-notify-event", on_leave)

        status_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.status_icon = Gtk.Image()
        self.status_icon.set_pixel_size(48)
        
        self.status_label = Gtk.Label(label="Initializing...")
        self.status_label.set_xalign(0.0)
        self.status_label.set_ellipsize(Pango.EllipsizeMode.END) 
        
        status_box.pack_start(self.status_icon, False, False, 0)
        status_box.pack_start(self.status_label, True, True, 0)
        self.status_eventbox.add(status_box)
        
        self.btn_disconnect = Gtk.Button()
        self.btn_disconnect.set_name("disconnect-button")
        self.btn_disconnect.set_relief(Gtk.ReliefStyle.NONE)
        self.btn_disconnect.set_size_request(32, 32)
        img = Gtk.Image.new_from_icon_name("network-disconnect-symbolic", Gtk.IconSize.BUTTON)
        img.set_pixel_size(18)
        self.btn_disconnect.set_image(img)
        self.btn_disconnect.set_always_show_image(True)
        self.btn_disconnect.set_tooltip_text("Disconnect")
        self.btn_disconnect.set_valign(Gtk.Align.CENTER)
        self.btn_disconnect.connect("clicked", self.on_disconnect_clicked)
        
        top_container.pack_start(self.status_eventbox, True, True, 0)
        top_container.pack_end(self.btn_disconnect, False, False, 0)
        vbox.pack_start(top_container, False, False, 0)

        vbox.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 0)

        # --- Network List Area ---
        self.listbox = Gtk.ListBox()
        self.listbox.set_name("network-list")
        self.listbox.connect("row-activated", self.on_network_clicked)
        
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.add(self.listbox)
        vbox.pack_start(scroll, True, True, 0)

# --- Bottom Buttons (Fixed width, Right aligned) ---
        bbox = Gtk.ButtonBox(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        bbox.set_layout(Gtk.ButtonBoxStyle.END)
        
        btn_refresh = Gtk.Button(label="Scan")
        btn_refresh.connect("clicked", lambda x: self.refresh_available_networks())
        
        btn_quit = Gtk.Button(label="Close")
        btn_quit.connect("clicked", Gtk.main_quit)
        
        bbox.add(btn_refresh)
        bbox.add(btn_quit)
        vbox.pack_start(bbox, False, False, 0)

        self.update_status()
        self.refresh_available_networks()
        
        self.client.connect("notify::active-connections", lambda *args: self.update_status())
        GLib.timeout_add_seconds(3, self.update_status)

    def _apply_css(self):
        css = b"""
        button { border-radius: 9px; min-width: 70px; }
        entry { border-radius: 9px; }

        #disconnect-button {
            min-width: 32px;
            min-height: 32px;
            padding: 0;
            border-radius: 9px;
            color: #e74c3c;
        }
        #disconnect-button:hover {
            background-color: rgba(231, 76, 60, 0.15);
        }
        
        #network-list { 
            background-color: #2e2e2e; 
            border-radius: 9px;
        }
        #network-list row { 
            background-color: transparent; 
            padding: 4px; 
            border-radius: 9px;
        }
        #network-list row:hover { 
            background-color: #3d3d3d; 
        }
        """
        provider = Gtk.CssProvider()
        provider.load_from_data(css)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def _get_wifi_device(self):
        for dev in self.client.get_devices():
            if dev.get_device_type() == NM.DeviceType.WIFI:
                return dev
        return None

    def _get_icon_name(self, strength):
        if strength >= 80: return "network-wireless-signal-excellent-symbolic"
        if strength >= 60: return "network-wireless-signal-good-symbolic"
        if strength >= 40: return "network-wireless-signal-ok-symbolic"
        if strength >= 20: return "network-wireless-signal-weak-symbolic"
        return "network-wireless-signal-none-symbolic"

    def update_status(self):
        dev = self._get_wifi_device()
        
        if not dev:
            self.status_icon.set_from_icon_name("network-wireless-disconnected-symbolic", Gtk.IconSize.DIALOG)
            self.status_label.set_markup("<b>No Wi-Fi Device Found</b>")
            self.btn_disconnect.set_visible(False)
            return True
            
        if dev.get_state() == NM.DeviceState.ACTIVATED:
            self.btn_disconnect.set_visible(True)
            ap = dev.get_active_access_point()
            if ap:
                ssid_b = ap.get_ssid()
                ssid = ssid_b.get_data().decode('utf-8', errors='ignore') if ssid_b else "Unknown"
                escaped_ssid = GLib.markup_escape_text(ssid)
                freq = ap.get_frequency()
                band = "6 GHz" if freq > 5900 else ("5 GHz" if freq > 4000 else "2.4 GHz")
                bitrate = ap.get_max_bitrate() / 1000
                
                markup = f"<span foreground='#8ab4f8' size='larger'><b>{escaped_ssid}</b></span>\n<small>{band}  |  {bitrate:.0f} Mbps</small>"
                self.status_label.set_markup(markup)
                self.status_icon.set_from_icon_name(self._get_icon_name(ap.get_strength()), Gtk.IconSize.DIALOG)
            else:
                self.status_label.set_markup("<span foreground='#8ab4f8' size='larger'><b>Connected</b></span>\n<small>No AP Info</small>")
                self.status_icon.set_from_icon_name("network-wireless-connected-symbolic", Gtk.IconSize.DIALOG)
        else:
            self.btn_disconnect.set_visible(False)
            self.status_label.set_markup("<b>Disconnected</b>\n<small>Select a network below</small>")
            self.status_icon.set_from_icon_name("network-wireless-disconnected-symbolic", Gtk.IconSize.DIALOG)
            
        return True

    def on_status_clicked(self, widget, event):
        dev = self._get_wifi_device()
        if dev and dev.get_state() == NM.DeviceState.ACTIVATED:
            ap = dev.get_active_access_point()
            active_conn = dev.get_active_connection()
            if ap and active_conn:
                conn = active_conn.get_connection()
                ssid_b = ap.get_ssid()
                ssid = ssid_b.get_data().decode('utf-8', errors='ignore') if ssid_b else "Unknown"
                
                self.hide()
                dialog = ConnectionDetailsDialog(self, dev, ap, ssid, conn)
                dialog.connect("destroy", lambda x: self.on_dialog_closed())

    def on_dialog_closed(self):
        self.update_status()
        self.refresh_available_networks()
        self.show()

    def on_disconnect_clicked(self, widget):
        dev = self._get_wifi_device()
        if dev and dev.get_state() == NM.DeviceState.ACTIVATED:
            active_conn = dev.get_active_connection()
            if active_conn:
                self.client.deactivate_connection_async(active_conn, None, self.on_deactivated, None)

    def on_deactivated(self, client, result, user_data):
        try:
            client.deactivate_connection_finish(result)
            self.update_status()
            self.refresh_available_networks()
        except Exception as e:
            print(f"Failed to deactivate: {e}")

    def refresh_available_networks(self):
        for row in self.listbox.get_children():
            self.listbox.remove(row)
            
        dev = self._get_wifi_device()
        if not dev:
            return
            
        try:
            dev.request_scan_async(None, lambda *args: None, None)
        except Exception:
            pass 
        
        aps = dev.get_access_points()
        seen_ssids = set()
        ap_list = []
        
        for ap in aps:
            ssid_b = ap.get_ssid()
            if not ssid_b: continue
            ssid = ssid_b.get_data().decode('utf-8', errors='ignore')
            if not ssid or ssid in seen_ssids: continue
            seen_ssids.add(ssid)
            ap_list.append(ap)
            
        ap_list.sort(key=lambda x: x.get_strength(), reverse=True)
        
        active_ssid = None
        if dev.get_state() == NM.DeviceState.ACTIVATED:
            active_ap = dev.get_active_access_point()
            if active_ap:
                ssid_b = active_ap.get_ssid()
                if ssid_b:
                    active_ssid = ssid_b.get_data().decode('utf-8', errors='ignore')
        
        for ap in ap_list:
            ssid_b = ap.get_ssid()
            ssid = ssid_b.get_data().decode('utf-8', errors='ignore')
            if ssid == active_ssid: continue
                
            strength = ap.get_strength()
            flags = ap.get_wpa_flags() | ap.get_rsn_flags()
            is_secure = flags != 0
            
            existing_conn = None
            for conn in self.client.get_connections():
                if conn.get_connection_type() == "802-11-wireless":
                    s_wifi = conn.get_setting_wireless()
                    if s_wifi:
                        c_ssid_b = s_wifi.get_ssid()
                        if c_ssid_b and c_ssid_b.get_data().decode('utf-8', errors='ignore') == ssid:
                            existing_conn = conn
                            break

            row = Gtk.ListBoxRow()
            row_data = {"device": dev, "ap": ap, "ssid": ssid, "is_secure": is_secure, "existing_conn": existing_conn}
            row.ap_data = row_data
            
            row_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            hbox.set_border_width(8)
            
            icon = Gtk.Image.new_from_icon_name(self._get_icon_name(strength), Gtk.IconSize.DND)
            label = Gtk.Label(label=ssid)
            label.set_xalign(0.0)
            
            hbox.pack_start(icon, False, False, 0)
            hbox.pack_start(label, True, True, 0)
            
            if existing_conn:
                btn_forget = Gtk.Button.new_from_icon_name("user-trash-symbolic", Gtk.IconSize.MENU)
                btn_forget.set_relief(Gtk.ReliefStyle.NONE)
                btn_forget.set_tooltip_text("Forget Network")
                btn_forget.connect("clicked", self.on_forget_clicked, existing_conn)
                hbox.pack_end(btn_forget, False, False, 0)
            elif is_secure:
                lock_icon = Gtk.Image.new_from_icon_name("network-wireless-encrypted-symbolic", Gtk.IconSize.MENU)
                hbox.pack_end(lock_icon, False, False, 0)
                
            row_vbox.pack_start(hbox, False, False, 0)
            
            revealer = Gtk.Revealer()
            revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN)
            revealer.set_transition_duration(250)
            
            auth_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            auth_box.set_margin_start(35)
            auth_box.set_margin_end(10)
            auth_box.set_margin_bottom(10)
            
            entry = Gtk.Entry()
            entry.set_visibility(False)
            entry.set_placeholder_text("Password")
            entry.set_width_chars(8) 
            
            btn_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            btn_connect = Gtk.Button(label="Connect")
            btn_cancel = Gtk.Button(label="Cancel")
            btn_connect.get_style_context().add_class("suggested-action")
            
            btn_box.pack_start(btn_cancel, False, False, 0)
            btn_box.pack_start(btn_connect, False, False, 0)
            
            auth_box.pack_start(entry, False, False, 0)
            auth_box.pack_start(btn_box, False, False, 0)
            revealer.add(auth_box)
            
            row_vbox.pack_start(revealer, False, False, 0)
            row.add(row_vbox)
            
            row_data["revealer"] = revealer
            row_data["entry"] = entry
            
            entry.connect("activate", self.on_inline_connect_clicked, row_data)
            btn_connect.connect("clicked", self.on_inline_connect_clicked, row_data)
            btn_cancel.connect("clicked", self.on_inline_cancel_clicked, row_data)
            
            self.listbox.add(row)
            
        self.listbox.show_all()

    def on_forget_clicked(self, button, conn):
        conn.delete_async(None, self.on_deleted, None)

    def on_deleted(self, conn, res, user_data):
        try:
            conn.delete_finish(res)
            GLib.idle_add(self.refresh_available_networks)
        except Exception as e:
            print(f"Failed to delete connection: {e}")

    def on_network_clicked(self, listbox, row):
        data = row.ap_data
        dev = data["device"]
        ap = data["ap"]
        ssid = data["ssid"]
        is_secure = data["is_secure"]
        existing_conn = data["existing_conn"]
        revealer = data["revealer"]
        entry = data["entry"]

        for r in self.listbox.get_children():
            if r != row:
                r.ap_data["revealer"].set_reveal_child(False)

        if existing_conn:
            self.client.activate_connection_async(existing_conn, dev, ap.get_path(), None, self.on_activated, ssid)
        else:
            if is_secure:
                is_open = revealer.get_reveal_child()
                revealer.set_reveal_child(not is_open)
                if not is_open: entry.grab_focus()
            else:
                self.create_and_connect(dev, ap, ssid, None)

    def on_inline_connect_clicked(self, widget, row_data):
        password = row_data["entry"].get_text()
        if password: self.create_and_connect(row_data["device"], row_data["ap"], row_data["ssid"], password)
        row_data["revealer"].set_reveal_child(False)

    def on_inline_cancel_clicked(self, widget, row_data):
        row_data["entry"].set_text("")
        row_data["revealer"].set_reveal_child(False)

    def create_and_connect(self, device, ap, ssid, password):
        profile = NM.SimpleConnection.new()
        
        s_con = NM.SettingConnection.new()
        s_con.set_property(NM.SETTING_CONNECTION_ID, ssid)
        s_con.set_property(NM.SETTING_CONNECTION_UUID, str(uuid.uuid4()))
        s_con.set_property(NM.SETTING_CONNECTION_TYPE, "802-11-wireless")
        profile.add_setting(s_con)
        
        s_wifi = NM.SettingWireless.new()
        s_wifi.set_property(NM.SETTING_WIRELESS_SSID, GLib.Bytes.new(ssid.encode('utf-8')))
        profile.add_setting(s_wifi)
        
        if password:
            s_wsec = NM.SettingWirelessSecurity.new()
            s_wsec.set_property(NM.SETTING_WIRELESS_SECURITY_KEY_MGMT, "wpa-psk")
            s_wsec.set_property(NM.SETTING_WIRELESS_SECURITY_PSK, password)
            profile.add_setting(s_wsec)
            
        s_ip4 = NM.SettingIP4Config.new()
        s_ip4.set_property(NM.SETTING_IP_CONFIG_METHOD, "auto")
        profile.add_setting(s_ip4)
        
        s_ip6 = NM.SettingIP6Config.new()
        s_ip6.set_property(NM.SETTING_IP_CONFIG_METHOD, "auto")
        profile.add_setting(s_ip6)
        
        self.client.add_and_activate_connection_async(profile, device, ap.get_path(), None, self.on_add_activated, ssid)

    def on_activated(self, client, result, ssid):
        try:
            client.activate_connection_finish(result)
            self.update_status()
            self.refresh_available_networks()
        except Exception as e:
            print(f"Failed to activate: {e}")

    def on_add_activated(self, client, result, ssid):
        try:
            client.add_and_activate_connection_finish(result)
            self.update_status()
            self.refresh_available_networks()
        except Exception as e:
            print(f"Failed to create and activate: {e}")

if __name__ == '__main__':
    app = WifiWindow()
    app.connect("destroy", Gtk.main_quit)
    app.show_all()
    try:
        Gtk.main()
    except KeyboardInterrupt:
        pass
