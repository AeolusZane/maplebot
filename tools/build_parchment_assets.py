"""Build small, lossless runtime PNGs; preserve all generated source artwork."""
import json
from pathlib import Path
from PySide6.QtGui import QImage
from PySide6.QtCore import Qt

root = Path(__file__).resolve().parents[1] / 'assets/ui/parchment'
output = root / 'runtime'
output.mkdir(exist_ok=True)
sizes = {name: 96 for name in ('maple','maple-muted','target','hp','mp','swords')}
sizes.update(avatar=192)
sizes.update({name: 627 for name in ('paper-v2','panel','selected','button-v2','frame-v2')})
manifest = {}
for name, edge in sizes.items():
    source = root / f'{name}.png'
    original = QImage(str(source))
    if original.isNull():
        raise RuntimeError(f'Missing asset: {source}')
    image = original.scaled(edge, edge, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    target = output / source.name
    if not image.save(str(target), 'PNG'):
        raise RuntimeError(f'Cannot save {target}')
    manifest[name] = dict(source_bytes=source.stat().st_size, runtime_bytes=target.stat().st_size,
                          width=image.width(), height=image.height(),
                          decoded_bytes=image.sizeInBytes(), source_decoded_bytes=original.sizeInBytes())
(output/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
for key in ('source_bytes','runtime_bytes','source_decoded_bytes','decoded_bytes'):
    print(f'{key}: {sum(row[key] for row in manifest.values()):,}')
