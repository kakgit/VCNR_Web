// Run: node --test tests/admin_library_upload.test.cjs
// Isolated dialog logic test; DOM/API doubles, not a browser or live server.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '..', 'app.js'), 'utf8').replace(/\r\n/g, '\n');

function functionSource(name) {
  const start = source.indexOf(`function ${name}(`);
  assert.ok(start >= 0, name);
  const end = source.indexOf('\n}\n', start) + 2;
  return (source.slice(start - 6, start) === 'async ' ? 'async ' : '') + source.slice(start, end);
}
function element(value = '') {
  return { value, dataset: {}, disabled: false, textContent: '', innerHTML: '', files: [],
    addEventListener() {}, click() {},
    classList: { add() {}, remove() {} }, setAttribute() {} };
}
function setup() {
  const c = { console, Set, Number, String, Array, JSON, FormData, Promise, Error, RegExp };
  for (const name of ['adminLibraryContentFile', 'adminLibraryContentFileName',
    'adminLibraryContentUploadPreview', 'adminLibraryUploadStartAtDisplay',
    'adminContentUploadStartAtDisplay', 'adminHelper']) c[name] = element();
  for (const name of ['setAdminLibraryUploadStartAtDisplay', 'setAdminContentUploadStartAtDisplay']) c[name] = () => {};
  c.adminLibrarySelectedPackageFiles = [];
  c.sent = null;
  c.apiUploadRequest = async (url, formData) => {
    c.sent = { url, entries: Array.from(formData.entries()) };
    return { item: {}, message: 'Library package uploaded.' };
  };
  for (const name of ['updateMovieCollections', 'renderAdminMovieList', 'renderAdminArchiveMovieList',
    'renderMovieGrid', 'syncDetailPanel']) c[name] = () => {};
  c.normalizeMovie = item => item;
  vm.createContext(c);
  for (const name of ['adminLibraryPackageEntryName', 'normalizeAdminLibraryPackageEntries',
    'summarizeAdminLibraryPackageSelection', 'missingAdminLibraryPackageChunks',
    'readAdminLibraryPackageManifest', 'uploadAdminLibraryContentPackageRemote']) {
    vm.runInContext(functionSource(name), c);
  }
  return c;
}

// A Library Converter package: manifest.json plus two chunked qualities.
function libraryManifest() {
  return {
    movie_id: 'dc', package_kind: 'library',
    qualities: [
      { quality_code: '480p', quality_label: '480P', sort_order: 1, chunk_count: 2,
        files: [
          { name: 'dc-480p-1.mp4', chunk_index: 1, media_kind: 'video', chunk_size: 4, sha256: 'a' },
          { name: 'dc-480p-2.mp4', chunk_index: 2, media_kind: 'video', chunk_size: 4, sha256: 'b' },
        ] },
      { quality_code: '720p', quality_label: '720P', sort_order: 2, chunk_count: 1,
        files: [{ name: 'dc-720p-1.mp4', chunk_index: 1, media_kind: 'video', chunk_size: 8, sha256: 'c' }] },
    ],
  };
}
// Real File objects, so FormData.append(file, name) works exactly as in a browser.
function fakeFile(name, text) {
  return new File([text === undefined ? `chunk:${name}` : text], name, { type: 'application/octet-stream' });
}
function selection(manifest, exclude = []) {
  const all = [{ name: 'manifest.json', text: JSON.stringify(manifest) },
    { name: 'dc-480p-1.mp4' }, { name: 'dc-480p-2.mp4' }, { name: 'dc-720p-1.mp4' }]
    .filter(entry => !exclude.includes(entry.name));
  return all.map(entry => {
    const file = fakeFile(entry.name, entry.text);
    return { file, relativePath: `content/${file.name}` };
  });
}

test('a valid Library Converter package is accepted and posted to the package route', async () => {
  const c = setup();
  const response = await c.uploadAdminLibraryContentPackageRemote('dc', selection(libraryManifest()));
  assert.equal(c.sent.url, '/admin/movies/dc/assets/library-content/package');
  assert.equal(c.sent.entries.filter(([k]) => k === 'files').length, 4);
  assert.equal(c.sent.entries.filter(([k]) => k === 'relative_paths').length, 4);
  assert.equal(response.message, 'Library package uploaded.');
});

test('a selection without manifest.json is rejected', async () => {
  const c = setup();
  const files = [fakeFile('dc-480p-1.mp4'), fakeFile('dc-720p-1.mp4')]
    .map(file => ({ file, relativePath: `content/${file.name}` }));
  await assert.rejects(
    () => c.uploadAdminLibraryContentPackageRemote('dc', files),
    /must contain manifest\.json/
  );
  assert.equal(c.sent, null);
});

test('a selection missing a chunk referenced by the manifest is rejected', async () => {
  const c = setup();
  // dc-720p-1.mp4 is referenced by the manifest but absent from the selection.
  const files = selection(libraryManifest(), ['dc-720p-1.mp4']);
  await assert.rejects(
    () => c.uploadAdminLibraryContentPackageRemote('dc', files),
    /missing files referenced by manifest\.json.*dc-720p-1\.mp4/is
  );
  assert.equal(c.sent, null);
});

test('a manifest referencing a missing subtitle chunk is rejected', async () => {
  const c = setup();
  const manifest = libraryManifest();
  manifest.qualities[1].subtitle_files = [{ name: 'dc-720p-1SUB.vtt', chunk_index: 1, media_kind: 'subtitle' }];
  await assert.rejects(
    () => c.uploadAdminLibraryContentPackageRemote('dc', selection(manifest)),
    /dc-720p-1SUB\.vtt/
  );
  assert.equal(c.sent, null);
});

test('a VCNR (encrypted) package is rejected for a library title', async () => {
  const c = setup();
  const manifest = libraryManifest();
  manifest.package_kind = 'vcnr';
  await assert.rejects(
    () => c.uploadAdminLibraryContentPackageRemote('dc', selection(manifest)),
    /need a Library Converter package/
  );
  assert.equal(c.sent, null);
});

test('an empty selection is rejected before any request', async () => {
  const c = setup();
  await assert.rejects(
    () => c.uploadAdminLibraryContentPackageRemote('dc', []),
    /select the content folder created by Library Converter/
  );
  assert.equal(c.sent, null);
});

test('the selection summary flags a missing manifest and counts chunks', () => {
  const c = setup();
  c.summarizeAdminLibraryPackageSelection([{ file: fakeFile('dc-480p-1.mp4') }]);
  assert.match(c.adminLibraryContentFileName.textContent, /1 files selected · 1 chunks · manifest\.json missing/);
  c.summarizeAdminLibraryPackageSelection(selection(libraryManifest()));
  assert.match(c.adminLibraryContentFileName.textContent, /4 files selected · 3 chunks$/);
  c.summarizeAdminLibraryPackageSelection([]);
  assert.equal(c.adminLibraryContentFileName.textContent, 'No folder selected');
});
