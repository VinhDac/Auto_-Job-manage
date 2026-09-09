/* Cầu nối runtime: máy đẩy xuống, màn hình vẽ lại. Không thư viện.
 *
 * Hợp đồng với HTML — view chỉ cần đặt đúng thuộc tính, không cần biết gì thêm:
 *
 *   [data-journal="search"]   khung nhật ký, lọc theo luồng ("" = tất cả)
 *   [data-progress="search"]  khung thanh tiến độ, lọc theo luồng
 *   [data-state]              chỗ hiện đang chạy / tạm dừng / chờ
 *   [data-act="run"|"pause"]  nút master
 *   [data-widget]             một ô; [data-expand] trong đó là nút mở to
 *
 * Không dùng polling: mở một kết nối SSE rồi để yên. Chạy 24/7 mà hỏi mỗi
 * giây thì một ngày là 86.400 lượt hỏi cho phần lớn là "chưa có gì mới".
 */
(() => {
  'use strict';

  const MAX_LINES = 200;          // trần DOM — chạy 24/7 không được phình
  const $ = (sel, root) => (root || document).querySelectorAll(sel);

  // ---------------------------------------------------------------- nhật ký
  const timeOf = (iso) => {
    const d = new Date(iso);
    return isNaN(d) ? '' : d.toTimeString().slice(0, 8);
  };

  function addLine(box, ev, atTop) {
    const want = box.dataset.journal;
    if (want && want !== ev.stream) return;

    const row = document.createElement('div');
    row.className = 'jline ' + (ev.level || 'info');
    row.innerHTML =
      '<span class=jtime></span>' +
      (want ? '' : '<span class=jstream></span>') +
      '<span class=jtext></span>';
    row.querySelector('.jtime').textContent = timeOf(ev.at);
    if (!want) row.querySelector('.jstream').textContent = ev.stream;
    row.querySelector('.jtext').textContent = ev.text;

    if (atTop) box.insertBefore(row, box.firstChild);
    else box.appendChild(row);
    while (box.childElementCount > MAX_LINES) {
      box.removeChild(atTop ? box.lastChild : box.firstChild);
    }
  }

  const journal = (ev) => $('[data-journal]').forEach((b) => addLine(b, ev, true));

  // --------------------------------------------------------------- tiến độ
  function drawProgress(box, all) {
    const want = box.dataset.progress;
    const rows = Object.entries(all).filter(([s]) => !want || s === want);
    if (!rows.length) { box.innerHTML = '<div class=pidle>không có việc đang chạy</div>'; return; }

    box.innerHTML = rows.map(([stream, p]) => {
      const count = p.total ? p.done + '/' + p.total : '';
      const width = p.total ? p.percent : 100;
      return '<div class="prow' + (p.total ? '' : ' spin') + '">' +
             '<div class=phead><b></b><span></span></div>' +
             '<div class=ptrack><i style="width:' + width + '%"></i></div></div>';
    }).join('');

    // Chữ đặt bằng textContent, KHÔNG nối vào chuỗi HTML: tên nguồn là dữ
    // liệu cào về, nối thẳng vào innerHTML là mở cửa cho thẻ lạ.
    box.querySelectorAll('.prow').forEach((el, i) => {
      const [stream, p] = rows[i];
      el.querySelector('b').textContent = want ? p.what : stream + ' — ' + p.what;
      el.querySelector('span').textContent = p.total ? p.done + '/' + p.total : '';
    });
  }

  const progress = (all) => $('[data-progress]').forEach((b) => drawProgress(b, all));

  // --------------------------------------------------------------- trạng thái
  const LABEL = { running: 'đang chạy', paused: 'tạm dừng', idle: 'chờ' };

  function setState(state) {
    document.body.dataset.run = state;
    $('[data-state]').forEach((el) => { el.textContent = LABEL[state] || state; });
    $('[data-act="pause"]').forEach((b) => {
      b.textContent = state === 'paused' ? 'Tiếp tục' : 'Tạm dừng';
    });
    $('[data-act="run"]').forEach((b) => { b.disabled = state === 'running'; });
  }

  // --------------------------------------------------------------- kết nối
  let live = null;

  function connect() {
    live = new EventSource('/events');

    live.onmessage = (msg) => {
      let m;
      try { m = JSON.parse(msg.data); } catch (e) { return; }
      if (m.type === 'hello') {
        $('[data-journal]').forEach((b) => { b.innerHTML = ''; });
        (m.events || []).forEach((e) => journal(e));
        progress(m.running || {});
        setState(m.state);
      } else if (m.type === 'event') {
        journal(m);
      } else if (m.type === 'progress') {
        // Một luồng xong -> hỏi lại toàn cảnh, vì khung này vẽ TẤT CẢ luồng
        // đang chạy chứ không phải riêng luồng vừa báo.
        fetch('/api/state').then((r) => r.json()).then((s) => {
          progress(s.running); setState(s.state);
        }).catch(() => {});
      }
    };

    // Đứt thì tự nối lại. Máy chạy 24/7, ngủ dậy mở máy là phải có sẵn.
    live.onerror = () => { live.close(); setTimeout(connect, 3000); };
  }

  // --------------------------------------------------------------- nút bấm
  function wire() {
    document.addEventListener('click', (e) => {
      const act = e.target.closest('[data-act]');
      if (act) {
        e.preventDefault();
        fetch('/api/' + act.dataset.act, { method: 'POST' })
          .then((r) => r.json()).then((s) => setState(s.state)).catch(() => {});
        return;
      }
      const grow = e.target.closest('[data-expand]');
      if (grow) {
        e.preventDefault();
        grow.closest('[data-widget]').classList.toggle('big');
      }
    });
    // Esc để thu ô đang mở to — mở to rồi không tìm thấy nút đóng là bí.
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') $('[data-widget].big').forEach((w) => w.classList.remove('big'));
    });
  }

  wire();
  connect();
})();
