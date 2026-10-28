// 빌드 도우미: Windows 의 화면 읽기(UIAutomationCore.dll) 안에 든 형식 정보로 interop DLL 을 만든다 (tlbimp 대신).
// 감시 프로그램(chatgpt_watch.cs)은 이걸 /link 로 컴파일해 필요한 형식만 exe 안에 넣으므로, 실행할 땐 이 DLL 이 필요 없다.
//   uia-interop.exe <UIAutomationCore.dll> <출력 폴더>   → <출력 폴더>\Interop.UIAutomationClient.dll
using System;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Runtime.InteropServices.ComTypes;

class UiaInterop : ITypeLibImporterNotifySink
{
    [DllImport("oleaut32.dll", CharSet = CharSet.Unicode, PreserveSig = false)]
    static extern void LoadTypeLibEx(string file, int regkind, out ITypeLib lib);

    static int Main(string[] args)
    {
        ITypeLib lib;
        LoadTypeLibEx(args[0], 2, out lib);          // REGKIND_NONE (등록은 건드리지 않음)
        const string name = "Interop.UIAutomationClient.dll";
        Environment.CurrentDirectory = args[1];      // 만든 DLL 은 지금 폴더에 저장된다
        var asm = new TypeLibConverter().ConvertTypeLibToAssembly(
            lib, name, TypeLibImporterFlags.SafeArrayAsSystemArray, new UiaInterop(), null, null,
            "Interop.UIAutomationClient", null);
        asm.Save(name);
        return 0;
    }

    public void ReportEvent(ImporterEventKind kind, int code, string msg) { }   // 형식마다 나오는 안내는 생략
    public Assembly ResolveRef(object lib) { return null; }
}
