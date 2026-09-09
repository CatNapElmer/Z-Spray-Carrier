' Double-click this to start the Z Spray Carrier app.
' Point a desktop shortcut at this file.
'
' Windows Script Host runs this with no console at all, so nothing flashes up
' and nothing is left on screen. It launches PowerShell hidden and with the
' execution policy bypassed for that one call only, so an unsigned script in a
' restricted-policy machine still runs.

Option Explicit

Dim shell, fso, here, script, cmd
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

here = fso.GetParentFolderName(WScript.ScriptFullName)
script = here & "\Start-ZSprayCarrier.ps1"

If Not fso.FileExists(script) Then
    MsgBox "Start-ZSprayCarrier.ps1 was not found next to this launcher." & vbCrLf & _
           "Expected: " & script, vbExclamation, "Z-Spray Carrier"
    WScript.Quit 1
End If

cmd = "powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File """ & script & """"

' 0 = hidden window, False = do not wait for it to finish
shell.Run cmd, 0, False
