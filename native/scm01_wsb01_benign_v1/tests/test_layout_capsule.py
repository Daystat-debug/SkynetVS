"""LAYOUT_CAPSULE01-08. Guest files are parsed/read as source, never imported/executed."""
import ast
import json
from pathlib import Path
import unittest
from dataclasses import replace
from . import test_contract as f
from .. import benign_contract as c
from .. import benign_layout as layout
from .. import benign_capsule as capsule

ROOT = Path(__file__).resolve().parents[1]


def spec():
    return layout.LayoutSpec('C:\\Users\\Operator\\Downloads\\Lab', 'C:\\HostState',
                             'C:\\Project\\SkynetVS', 'C:\\Users\\Operator\\Downloads', (), f.RID)


def fake_runtime():
    files = {'f%02d.dll' % i: b'fake' for i in range(33)}
    files.update({'python.exe': b'fake_exe', 'python313._pth': capsule.LOCKED_PTH,
                  'python313.zip': b'fake_stdlib'})
    rows = [{'path': n, 'size_bytes': len(b), 'sha256': c.sha(b)} for n, b in sorted(files.items())]
    files['runtime_manifest.json'] = (json.dumps({'payload_files': rows}, ensure_ascii=False,
        sort_keys=True, separators=(',', ':')) + '\n').encode()
    return files


class LayoutCapsuleTests(unittest.TestCase):
    def test_LAYOUT_CAPSULE01_fixed_mapping_xml(self):
        bound = layout.plan_layout(spec()); raw = layout.render_wsb(bound, 'a' * 64)
        self.assertEqual(raw.count(b'<MappedFolder>'), 4)
        self.assertEqual(raw.count(b'<ReadOnly>true</ReadOnly>'), 3)
        self.assertEqual(raw.count(b'<ReadOnly>false</ReadOnly>'), 1)
        self.assertIn(b'<Networking>Disable</Networking>', raw)
        self.assertIn(b'<ProtectedClient>Enable</ProtectedClient>', raw)
        self.assertNotIn(f.request(), raw)

    def test_LAYOUT_CAPSULE02_overlap_refused(self):
        for candidate in (replace(spec(), host_state='C:\\Users\\Operator\\Downloads\\Lab'),
                          replace(spec(), lab_parent='C:\\Project\\SkynetVS\\Lab'),
                          replace(spec(), excluded=('C:\\Users\\Operator\\Downloads\\Lab',))):
            with self.subTest(candidate=candidate), self.assertRaises(c.BenignError): layout.plan_layout(candidate)

    def test_LAYOUT_CAPSULE03_lexical_alias_paths(self):
        for p in ('\\\\server\\x', 'C:\\Lab\\..\\X', 'C:\\Lab\\x:stream', 'C:\\Lab\\CON.txt',
                  'C:\\Lab\\x.', 'C:\\Lab\\short~1', 'C:/Lab/X', 'C:\\Lab\\.venv\\X'):
            with self.subTest(path=p), self.assertRaises(c.BenignError): layout.plan_layout(replace(spec(), lab_parent=p))
        # Filesystem reparse detection is separately exercised by WINDOWS_BINDINGS07.

    def test_LAYOUT_CAPSULE04_exact_capsule_subset(self):
        source = {n: (ROOT / n).read_bytes() for n in capsule.SOURCE_PATHS}
        plan = capsule.build_capsule(source, capsule._fake_runtime_inventory(fake_runtime()))
        self.assertEqual(set(dict(plan.members)), set(capsule.CAPSULE_MEMBERS))
        self.assertEqual(len(plan.members), 8)
        self.assertNotIn('tests/', ''.join(dict(plan.members)))
        bad = dict(source); bad['extra.py'] = bad.pop('tests/test_contract.py')
        with self.assertRaises(c.BenignError): capsule.build_capsule(bad, plan.runtime)

    def test_LAYOUT_CAPSULE05_retained_inventory_not_version_guess(self):
        files = fake_runtime(); fake = capsule._fake_runtime_inventory(files)
        self.assertEqual(len(fake.files), 37); self.assertEqual(fake.provenance, 'OFFLINE_MODEL')
        with self.assertRaises(c.BenignError): capsule.validate_runtime_inventory(files)
        for bad in (dict(files, unknown=b'x'), {k: v for k, v in files.items() if k != 'python.exe'}):
            with self.subTest(count=len(bad)), self.assertRaises(c.BenignError): capsule._fake_runtime_inventory(bad)

    def test_LAYOUT_CAPSULE06_static_bootstrap_copy_before_interpreter(self):
        text = (ROOT / 'payload/guest_bootstrap.ps1').read_text()
        self.assertLess(text.index('exit 92'), text.index('$InputRoot'))
        self.assertLess(text.index("throw 'Source hash mismatch.'"), text.index('& $Python'))
        self.assertLess(text.index("throw 'Local copy identity mismatch.'"), text.index('& $Python'))
        self.assertIn('[System.IO.FileMode]::CreateNew', text)
        self.assertIn('$Stream.Flush($true)', text)
        # Static source ordering, NOT execution or PowerShell parser acceptance.

    def test_LAYOUT_CAPSULE07_pth_and_import_path_source(self):
        self.assertEqual(capsule.LOCKED_PTH, b'python313.zip\r\n.\r\n')
        guest = (ROOT / 'payload/guest_entry.py').read_text()
        tree = ast.parse(guest)
        self.assertTrue(tree.body)
        self.assertNotIn('sys.path.append', guest)
        self.assertIn("raise SystemExit(92)", guest)
        bootstrap = (ROOT / 'payload/guest_bootstrap.ps1').read_text()
        self.assertIn('& $Python -I -S -B -X utf8 $Entry', bootstrap)
        self.assertNotIn('Set-Content', bootstrap)

    def test_LAYOUT_CAPSULE08_settings_no_silent_fallback(self):
        bad = replace(spec(), supported_settings=layout.SETTINGS[:-1])
        with self.assertRaises(c.BenignError): layout.plan_layout(bad)
        bound = layout.plan_layout(spec())
        with self.assertRaises(c.BenignError): layout.render_wsb(replace(bound, settings=()), 'a' * 64)
        with self.assertRaises(c.BenignError): layout.render_wsb(bound, 'not-a-pin')


class GuestLoaderSource117Tests(unittest.TestCase):
    def plan_inputs(self):
        source = {n: (ROOT / n).read_bytes() for n in capsule.SOURCE_PATHS}
        runtime = capsule._fake_runtime_inventory(fake_runtime())
        built = capsule.build_capsule(source, runtime)
        fields = c.parse_benign('request', f.request()).fields
        fields.update(capsule_sha256=built.capsule_sha256, runtime_sha256=runtime.tree_sha256,
                      source_sha256=built.source_sha256)
        request = c.serialize_benign('request', fields)
        return request, built, runtime

    def test_REG30_guest_load_plan_exact_eight_member_graph(self):
        request, built, runtime = self.plan_inputs()
        plan = capsule.prepare_guest_load(request, built.manifest, dict(built.members), runtime)
        self.assertEqual(len(plan.module_names), 8); self.assertEqual(plan.evidence_domain, 'OFFLINE_MODEL')
        descriptor = capsule.checked_guest_descriptor(plan)
        self.assertEqual(descriptor['scope'], 'VERIFIED_BYTE_PLAN_NOT_AUTHORITY')
        self.assertEqual(descriptor['capsule_sha256'], built.capsule_sha256)

    def test_REG31_guest_changed_member_and_alias_refused(self):
        request, built, runtime = self.plan_inputs(); members = dict(built.members)
        first = sorted(members)[0]; members[first] += b'x'
        with self.assertRaises(c.BenignError): capsule.prepare_guest_load(request, built.manifest, members, runtime)
        members = dict(built.members); members['app/../bad.py'] = b'x'
        with self.assertRaises(c.BenignError): capsule.prepare_guest_load(request, built.manifest, members, runtime)

    def test_REG32_guest_relative_imports_resolve_to_capsule(self):
        request, built, runtime = self.plan_inputs()
        plan = capsule.prepare_guest_load(request, built.manifest, dict(built.members), runtime)
        edges = capsule.guest_dependency_check(plan)
        self.assertIn(('native.scm01_wsb01_benign_v1.payload.guest_entry',
                       'native.scm01_wsb01_benign_v1.benign_capsule'), edges)
        self.assertTrue(all(n in plan.module_names for _, n in edges))

    def test_REG33_no_execution_in_loader_plan_tests(self):
        import sys
        request, built, runtime = self.plan_inputs()
        plan = capsule.prepare_guest_load(request, built.manifest, dict(built.members), runtime)
        from ..benign_runtime_gate import RuntimeClosed
        with self.assertRaises(RuntimeClosed): capsule.load_checked_guest_modules(plan, {'approved': True})
        self.assertNotIn('native.scm01_wsb01_benign_v1.payload.guest_entry', sys.modules)

    def test_REG34_standalone_loader_uses_canonical_package_names(self):
        text = (ROOT / 'payload/guest_entry.py').read_text()
        tree = ast.parse(text); functions = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
        self.assertIn('_load_capsule_byte_graph', functions)
        loader = ast.get_source_segment(text, functions['_load_capsule_byte_graph'])
        self.assertIn("importlib.import_module(prefix + '.payload.guest_entry')", loader)
        self.assertIn("sources[module.__name__]", loader)
        self.assertNotIn('sys.path.insert', loader); self.assertNotIn('SourceFileLoader(', loader)
        self.assertLess(loader.index("'loader_member_pin'"), loader.index('sys.meta_path.insert'))
        # Static assertions only. Neither this loader nor the guest payload executes.

    def test_REG35_bootstrap_and_python_share_exact_capsule_members(self):
        ps_text = (ROOT / 'payload/guest_bootstrap.ps1').read_text()
        guest_text = (ROOT / 'payload/guest_entry.py').read_text()
        self.assertEqual(len(capsule.CAPSULE_MEMBERS), 8)
        for name in capsule.CAPSULE_MEMBERS:
            self.assertIn("'" + name + "'", ps_text)
            self.assertIn("'" + name + "'", guest_text)
        self.assertLess(ps_text.index('exit 92'), ps_text.index('$InputRoot'))

    def test_REG36_guest_manifest_rows_and_runtime_mismatch_refused(self):
        request, built, runtime = self.plan_inputs()
        wrong = c.parse_benign('request', request).fields; wrong['runtime_sha256'] = '0' * 64
        with self.assertRaises(c.BenignError):
            capsule.prepare_guest_load(c.serialize_benign('request', wrong), built.manifest, dict(built.members), runtime)
        rows = c.parse_json(built.manifest); rows['files'] = list(reversed(rows['files']))
        raw = c.canonical(rows); wrong = c.parse_benign('request', request).fields; wrong['capsule_sha256'] = c.sha(raw)
        with self.assertRaises(c.BenignError):
            capsule.prepare_guest_load(c.serialize_benign('request', wrong), raw, dict(built.members), runtime)

    def test_REG43_capsule_nondictionary_rows_fail_as_contract_error(self):
        request, built, runtime = self.plan_inputs()
        for invalid in (None, 42, [], True, 'wrong'):
            rows = c.parse_json(built.manifest); rows['files'][0] = invalid
            raw = c.canonical(rows); req = c.parse_benign('request', request).fields
            req['capsule_sha256'] = c.sha(raw)
            with self.subTest(invalid=invalid), self.assertRaises(c.BenignError):
                capsule.prepare_guest_load(c.serialize_benign('request', req), raw,
                                           dict(built.members), runtime)

    def test_REG44_standalone_decoder_source_has_bounded_depth_and_numbers(self):
        # Static-only source review. No payload import or function execution.
        text = (ROOT / 'payload/guest_entry.py').read_text()
        tree = ast.parse(text)
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                    and n.name == '_load_capsule_byte_graph')
        nested = {n.name: n for n in node.body if isinstance(n, ast.FunctionDef)}
        self.assertIn('shape', nested); self.assertIn('reject_number', nested)
        decoder = ast.get_source_segment(text, nested['decode'])
        self.assertIn("depth <= 16", decoder)
        self.assertIn('parse_float=reject_number', decoder)
        self.assertIn('parse_constant=reject_number', decoder)
        self.assertLess(decoder.index('loader_depth'), decoder.index('obj = json.loads'))


class GuestFirstProcess118Tests(unittest.TestCase):
    def inputs(self):
        raw,built,runtime=GuestLoaderSource117Tests().plan_inputs()
        plan=capsule.prepare_guest_load(raw,built.manifest,dict(built.members),runtime)
        bootstrap=(ROOT/'payload/guest_bootstrap.ps1').read_bytes()
        startup=capsule.build_guest_startup(plan,bootstrap)
        return plan,bootstrap,startup

    def test_REG63_guest_fixed_startup_four_arguments(self):
        plan,bootstrap,startup=self.inputs()
        self.assertEqual(len(startup.argv()),4)
        self.assertEqual(capsule.parse_guest_startup_args(startup.argv()),startup)
        checked=capsule.validate_guest_startup(plan,startup.argv(),bootstrap,plan.runtime_root+'\\python.exe',
                  plan.capsule_root+'\\app\\native\\scm01_wsb01_benign_v1\\payload\\guest_entry.py')
        self.assertEqual(checked['scope'],'CHECKED_DATA_NOT_AUTHORITY')

    def test_REG64_guest_argv_extra_cli_flags_not_authority(self):
        _p,_b,data=self.inputs()
        for argv in ([],list(data.argv())+['approved=true'],['--run-id']+list(data.argv()),
                     ['--unsafe',*data.argv()[1:]],True,'anything'):
            with self.subTest(argv=argv),self.assertRaises(c.BenignError):capsule.parse_guest_startup_args(argv)

    def test_REG65_guest_startup_request_hash_drift_refused(self):
        plan,bootstrap,data=self.inputs()
        for index in range(4):
            args=list(data.argv());args[index]='0'*len(args[index])
            with self.subTest(index=index),self.assertRaises(c.BenignError):
                capsule.validate_guest_startup(plan,args,bootstrap,plan.runtime_root+'\\python.exe',
                   plan.capsule_root+'\\app\\native\\scm01_wsb01_benign_v1\\payload\\guest_entry.py')

    def test_REG66_guest_startup_bootstrap_pin_refused(self):
        plan,bootstrap,data=self.inputs()
        with self.assertRaises(c.BenignError):
            capsule.validate_guest_startup(plan,data.argv(),bootstrap+b'changed',plan.runtime_root+'\\python.exe',
                 plan.capsule_root+'\\app\\native\\scm01_wsb01_benign_v1\\payload\\guest_entry.py')

    def test_REG67_guest_startup_fixed_local_paths(self):
        plan,bootstrap,data=self.inputs();script=plan.capsule_root+'\\app\\native\\scm01_wsb01_benign_v1\\payload\\guest_entry.py'
        for exe,entry in (('C:\\Project\\SkynetVS\\.venv\\Scripts\\python.exe',script),
                          (plan.runtime_root+'\\python.exe','C:\\Other\\guest_entry.py')):
            with self.subTest(exe=exe,entry=entry),self.assertRaises(c.BenignError):
                capsule.validate_guest_startup(plan,data.argv(),bootstrap,exe,entry)

    def test_REG68_guest_first_route_gate_before_io_source(self):
        tree=ast.parse((ROOT/'payload/guest_entry.py').read_text())
        node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_guest_first_process')
        first=next(n for n in node.body if isinstance(n,ast.Expr) and isinstance(n.value,ast.Call))
        self.assertEqual(first.value.func.id,'_require_local_guest_ingress')
        gate=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_require_local_guest_ingress')
        self.assertTrue(any(isinstance(n,ast.Raise) for n in gate.body))
        # No compile/exec/import of this guest module in any test.

    def test_REG69_guest_pin_reads_precede_byte_loader_source(self):
        text=(ROOT/'payload/guest_entry.py').read_text();tree=ast.parse(text)
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_guest_first_process')
        src=ast.get_source_segment(text,fn)
        self.assertLess(src.index("_early_read(input_root+'\\\\request.json'"),src.index('_load_capsule_byte_graph('))
        self.assertLess(src.index("'guest_first_runtime_total'"),src.index('_load_capsule_byte_graph('))
        self.assertLess(src.index('validate_guest_startup('),src.index('entry.main_fixed_guest('))
        self.assertIn('loader_plan=plan',src)

    def test_REG70_guest_plan_not_carried_as_permit_attribute(self):
        text=(ROOT/'payload/guest_entry.py').read_text()
        self.assertNotIn('permit.loader_plan',text)
        self.assertIn('plan = loader_plan',text)
        self.assertIn('prepare_guest_load(plan.request, plan.capsule_manifest',text)

    def test_REG71_ps_fixed_argument_order_source(self):
        text=(ROOT/'payload/guest_bootstrap.ps1').read_text()
        command='& $Python -I -S -B -X utf8 $Entry $RunId $RequestSha $CapsuleSha $BootstrapSha'
        self.assertEqual(text.count(command),1)
        self.assertLess(text.index('$RequestSha = Get-ByteHash $RequestBytes'),text.index(command))
        self.assertLess(text.index('$BootstrapSha = Get-ByteHash $BootstrapBytes'),text.index(command))
        self.assertLess(text.index('exit 92'),text.index('$InputRoot'))

    def test_REG72_ps_no_added_runtime_paths_or_issuer(self):
        text=(ROOT/'payload/guest_bootstrap.ps1').read_text()
        for token in ('Start-Process','Set-Acl','New-Service','RegisterTaskDefinition','Invoke-WebRequest'):
            self.assertNotIn(token,text)
        self.assertIn('$InterpreterReturned = $true',text)
        self.assertEqual(text.count("& 'C:\\Windows\\System32\\shutdown.exe' /s /t 0"),1)

    def test_REG73_early_decoders_source_identical_not_guest_execution(self):
        from .. import benign_worker
        import inspect
        guest_tree=ast.parse((ROOT/'payload/guest_entry.py').read_text())
        host_tree=ast.parse(inspect.getsource(benign_worker))
        for name in ('_early_decode','_early_read'):
            a=next(n for n in guest_tree.body if isinstance(n,ast.FunctionDef) and n.name==name)
            b=next(n for n in host_tree.body if isinstance(n,ast.FunctionDef) and n.name==name)
            self.assertEqual(ast.dump(a,include_attributes=False),ast.dump(b,include_attributes=False))

    def test_REG74_no_new_guest_module_or_member(self):
        plan,_b,_data=self.inputs();edges=capsule.guest_dependency_check(plan)
        self.assertEqual(len(plan.members),8)
        self.assertEqual(set(dict(plan.members)),set(capsule.CAPSULE_MEMBERS))
        self.assertEqual(len(capsule.SOURCE_PATHS),32)
        self.assertTrue(edges)

    def test_REG75_guest_startup_data_never_opens_gates(self):
        from .. import benign_runtime_gate as gate
        plan,_bootstrap,data=self.inputs()
        for value in (plan,data,data.argv(),{'loader_plan':plan,'approved':True}):
            with self.subTest(value=type(value).__name__),self.assertRaises(gate.RuntimeClosed):
                gate.require_benign_run_authority(value)

    def test_REG76_guest_not_in_modules_after_all_host_checks(self):
        import sys
        self.inputs()
        self.assertNotIn('native.scm01_wsb01_benign_v1.payload.guest_entry',sys.modules)
        self.assertNotIn('ctypes',sys.modules)


class GuestEagerImportReview119Tests(unittest.TestCase):
    """REG87-REG92: exact AST model of module-level import statements, not guest execution.
    Function-local imports are deliberately excluded: declaring them does not load helpers.
    """
    PREFIX = 'native.scm01_wsb01_benign_v1'

    def loader_imports(self, text):
        fn = next(n for n in ast.parse(text).body if isinstance(n, ast.FunctionDef) and
                  n.name == '_load_capsule_byte_graph')
        imports = []
        for n in ast.walk(fn):
            if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and
                    isinstance(n.func.value, ast.Name) and n.func.value.id == 'importlib' and
                    n.func.attr == 'import_module'): continue
            arg = n.args[0]
            if isinstance(arg, ast.Name) and arg.id == 'prefix': target = self.PREFIX
            else:
                self.assertIsInstance(arg, ast.BinOp); self.assertIsInstance(arg.op, ast.Add)
                self.assertIsInstance(arg.left, ast.Name); self.assertEqual(arg.left.id, 'prefix')
                self.assertIsInstance(arg.right, ast.Constant); self.assertIsInstance(arg.right.value, str)
                target = self.PREFIX + arg.right.value
            imports.append((n.lineno, target))
        return fn, sorted(imports)

    def eager_modules(self, text):
        import importlib.util
        sources = {capsule.guest_module_name('app/' + capsule.TARGET + name): (ROOT / name).read_text()
                   for name in capsule.GUEST_MODULES}
        sources[self.PREFIX + '.payload.guest_entry'] = text
        def imports_at_module_level(stmts, package):
            for n in stmts:
                if isinstance(n, ast.ImportFrom) and n.level:
                    target = importlib.util.resolve_name('.' * n.level + (n.module or ''), package)
                    if target.startswith('native.'):
                        yield target
                        if not n.module:
                            for alias in n.names: yield target + '.' + alias.name
                elif isinstance(n, ast.If) and isinstance(n.test, ast.Name) and n.test.id == '__package__':
                    yield from imports_at_module_level(n.body, package)
                # Function/class bodies and standalone __main__ branch are not executed by this model.
        visited = set()
        def visit(name):
            if name in visited: return
            visited.add(name)
            if name not in sources:
                self.assertIn(name, ('native', self.PREFIX + '.payload')); return
            package = name if name == self.PREFIX else name.rsplit('.', 1)[0]
            for target in imports_at_module_level(ast.parse(sources[name]).body, package): visit(target)
        for _line, name in self.loader_imports(text)[1]: visit(name)
        return visited

    def test_REG87_loader_explicitly_imports_needed_helpers(self):
        text = (ROOT / 'payload/guest_entry.py').read_text()
        imports = self.loader_imports(text)[1]; names = [n for _, n in imports]
        for suffix in ('.benign_capsule', '.benign_layout'):
            self.assertEqual(names.count(self.PREFIX + suffix), 1)
            self.assertLess(names.index(self.PREFIX + suffix), names.index(self.PREFIX + '.payload.guest_entry'))

    def test_REG88_eager_graph_satisfies_immediate_module_lookups(self):
        text = (ROOT / 'payload/guest_entry.py').read_text()
        loaded = self.eager_modules(text)
        fn = next(n for n in ast.parse(text).body if isinstance(n, ast.FunctionDef) and n.name == '_guest_first_process')
        required = {n.slice.value for n in ast.walk(fn) if isinstance(n, ast.Subscript) and
                    isinstance(n.value, ast.Attribute) and isinstance(n.value.value, ast.Name) and
                    n.value.value.id == 'sys' and n.value.attr == 'modules' and isinstance(n.slice, ast.Constant)}
        self.assertEqual(required, {self.PREFIX + '.benign_capsule', self.PREFIX + '.benign_layout'})
        self.assertTrue(required <= loaded)

    def test_REG89_missing_eager_capsule_import_detected_without_execution(self):
        text = (ROOT / 'payload/guest_entry.py').read_text()
        line = "        importlib.import_module(prefix + '.benign_capsule')\n"
        self.assertEqual(text.count(line), 1)
        old_shape = text.replace(line, '')  # In-memory source mutation only; no file change/import.
        self.assertNotIn(self.PREFIX + '.benign_capsule', self.eager_modules(old_shape))
        # Existing function-local from-imports must not be mistaken for eager loading.
        self.assertIn('from ..benign_capsule import', old_shape)

    def test_REG90_eager_targets_stay_inside_eight_member_graph(self):
        text = (ROOT / 'payload/guest_entry.py').read_text()
        names = {capsule.guest_module_name(p) for p in capsule.CAPSULE_MEMBERS}
        self.assertEqual(len(names), 8)
        self.assertTrue({n for _, n in self.loader_imports(text)[1]} <= names)
        self.assertTrue(self.eager_modules(text) <= names | {'native', self.PREFIX + '.payload'})

    def test_REG91_hashes_and_finder_precede_eager_helper_imports(self):
        text = (ROOT / 'payload/guest_entry.py').read_text(); fn, imports = self.loader_imports(text)
        pin = next(n.lineno for n in ast.walk(fn) if isinstance(n, ast.Call) and
                   any(isinstance(a, ast.Constant) and a.value == 'loader_member_pin' for a in n.args))
        finder = next(n.lineno for n in ast.walk(fn) if isinstance(n, ast.Call) and
                      isinstance(n.func, ast.Attribute) and n.func.attr == 'insert' and
                      isinstance(n.func.value, ast.Attribute) and n.func.value.attr == 'meta_path')
        helpers = [line for line, name in imports if name in
                   (self.PREFIX + '.benign_capsule', self.PREFIX + '.benign_layout')]
        self.assertEqual(len(helpers), 2)
        self.assertLess(pin, finder); self.assertTrue(all(finder < line for line in helpers))

    def test_REG92_guest_ingress_barriers_remain_unconditional(self):
        import sys
        text = (ROOT / 'payload/guest_entry.py').read_text()
        fns = {n.name: n for n in ast.parse(text).body if isinstance(n, ast.FunctionDef)}
        self.assertEqual(len(fns['_require_local_guest_ingress'].body), 1)
        self.assertIsInstance(fns['_require_local_guest_ingress'].body[0], ast.Raise)
        for name in ('_guest_first_process', '_load_capsule_byte_graph'):
            body = fns[name].body
            first = body[1] if isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) else body[0]
            self.assertIsInstance(first, ast.Expr); self.assertIsInstance(first.value, ast.Call)
            self.assertEqual(first.value.func.id, '_require_local_guest_ingress')
        self.assertNotIn(self.PREFIX + '.payload.guest_entry', sys.modules)
        self.assertNotIn('ctypes', sys.modules)
