import sys, shutil
sys.path.insert(0, 'src')
from cx_programmer_mcp.cxp_decode import decode_cxp, encode_cxp
from cx_programmer_mcp.cxt import CxtProject

# Decode cerdas_cermat sebagai template kosong
raw = open('examples/cerdas_cermat.cxp', 'rb').read()
p = CxtProject.from_path('examples/cerdas_cermat.cxp')

# Hapus semua rung dari Section1 milik NewProgram1
rungs = p.get_rungs('NewProgram1', 'Section1', include_empty=True)
print(f'Rungs in cermat before clear: {len(rungs)}')

# Clear semua rung dengan replace ke kosong
for i in range(len(rungs) - 1, -1, -1):
    if not rungs[i]['empty']:
        p.replace_rung('NewProgram1', 'Section1', i, [])

rungs_after = p.get_rungs('NewProgram1', 'Section1', include_empty=False)
print(f'Rungs after clear: {len(rungs_after)}')

# Simpan sebagai template
p.save_cxt('project/template_kosong.cxt', backup=False)
p.save_cxp('project/template_kosong.cxp', backup=False)
print('Template kosong disimpan')
