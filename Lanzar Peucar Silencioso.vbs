Set objShell = WScript.CreateObject("WScript.Shell")
Set objFSO = CreateObject("Scripting.FileSystemObject")

' Obtener la carpeta actual donde está el script
strPath = Wscript.ScriptFullName
Set objFile = objFSO.GetFile(strPath)
strFolder = objFSO.GetParentFolderName(objFile) 

' Establecer la carpeta de trabajo
objShell.CurrentDirectory = strFolder

' Ejecutar main.py usando py o python (el estilo de ventana 0 oculta la consola negra automáticamente)
On Error Resume Next
Err.Clear
objShell.Run "py main.py", 0, False

If Err.Number <> 0 Then
    ' Si falló con py, intentar con python
    Err.Clear
    objShell.Run "python main.py", 0, False
    If Err.Number <> 0 Then
        MsgBox "No se pudo encontrar Python en el sistema. Asegúrate de tener Python instalado y añadido al PATH.", 16, "Error de Ejecución"
    End If
End If
