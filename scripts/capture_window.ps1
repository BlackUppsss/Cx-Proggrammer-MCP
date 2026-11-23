param(
    [Parameter(Mandatory=$true)]
    [string]$TitleContains,
    
    [Parameter(Mandatory=$true)]
    [string]$OutputPath
)

Add-Type @"
using System;
using System.Threading;
using System.Runtime.InteropServices;
using System.Text;
using System.Drawing;
using System.Drawing.Imaging;

public class WinCaptureHelper {
    [DllImport("user32.dll", SetLastError = true)]
    public static extern IntPtr OpenDesktop(string lpszDesktop, uint dwFlags, bool fInherit, uint dwDesiredAccess);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool SetThreadDesktop(IntPtr hDesktop);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool CloseDesktop(IntPtr hDesktop);

    public delegate bool CallBack(IntPtr hwnd, int lParam);
    [DllImport("user32.dll")]
    public static extern int EnumDesktopWindows(IntPtr hDesktop, CallBack x, int y);

    [DllImport("user32.dll")]
    public static extern int GetWindowText(IntPtr hWnd, StringBuilder lpString, int nMaxCount);

    [DllImport("user32.dll")]
    public static extern bool IsWindowVisible(IntPtr hWnd);

    [DllImport("user32.dll")]
    public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);

    [StructLayout(LayoutKind.Sequential)]
    public struct RECT {
        public int Left;
        public int Top;
        public int Right;
        public int Bottom;
    }

    public static string Capture(string titleFilter, string outPath) {
        string status = "NOT_FOUND";
        Thread t = new Thread(() => {
            IntPtr hDesk = OpenDesktop("Default", 0, false, 0x01FF);
            if (hDesk == IntPtr.Zero) {
                status = "OPEN_DESKTOP_FAILED";
                return;
            }
            if (SetThreadDesktop(hDesk)) {
                IntPtr targetHwnd = IntPtr.Zero;
                RECT targetRect = new RECT();
                string matchedTitle = "";

                System.Collections.Generic.List<string> visibleTitles = new System.Collections.Generic.List<string>();
                EnumDesktopWindows(hDesk, (hwnd, lparam) => {
                    if (IsWindowVisible(hwnd)) {
                        StringBuilder sb = new StringBuilder(512);
                        GetWindowText(hwnd, sb, 512);
                        string tTitle = sb.ToString();
                        if (!string.IsNullOrEmpty(tTitle)) {
                            visibleTitles.Add(tTitle);
                        }
                        if (tTitle.IndexOf(titleFilter, StringComparison.OrdinalIgnoreCase) >= 0) {
                            targetHwnd = hwnd;
                            matchedTitle = tTitle;
                            GetWindowRect(hwnd, out targetRect);
                            return false;
                        }
                    }
                    return true;
                }, 0);

                if (targetHwnd != IntPtr.Zero) {
                    int w = targetRect.Right - targetRect.Left;
                    int h = targetRect.Bottom - targetRect.Top;
                    if (w > 0 && h > 0) {
                        using (Bitmap bmp = new Bitmap(w, h)) {
                            using (Graphics g = Graphics.FromImage(bmp)) {
                                g.CopyFromScreen(targetRect.Left, targetRect.Top, 0, 0, new Size(w, h));
                            }
                            System.IO.FileInfo fi = new System.IO.FileInfo(outPath);
                            if (fi.Directory != null && !fi.Directory.Exists) {
                                fi.Directory.Create();
                            }
                            bmp.Save(outPath, ImageFormat.Png);
                            status = "OK:" + matchedTitle;
                        }
                    } else {
                        status = "ZERO_SIZE";
                    }
                } else {
                    status = "NOT_FOUND:" + string.Join(" | ", visibleTitles);
                }

            } else {
                status = "SET_THREAD_DESKTOP_FAILED";
            }
            CloseDesktop(hDesk);
        });
        t.SetApartmentState(ApartmentState.STA);
        t.Start();
        t.Join();
        return status;
    }
}
"@ -ReferencedAssemblies System.Drawing

$res = [WinCaptureHelper]::Capture($TitleContains, $OutputPath)
Write-Output $res
