# PERF-H1 Report — `Architecture.component_of` linear scan → membership index

> Vị trí đề xuất trong repo: `reports/perf-h1/`
> Trạng thái: **Đã kiểm chứng đầy đủ trong môi trường sandbox** (Python 3, Ubuntu 24) trên clone của `lemduc/arcade-agent@20d3728` (main). **Chưa apply vào repo này** — patch đính kèm, apply bằng 1 lệnh (xem §6).
> Files đi kèm: `h1-membership-index.patch` (bản vá, +17/−6, 1 file) · `bench_h1.py` (script tái tạo toàn bộ số liệu).

---

## 1. Vấn đề

`Architecture.component_of()` trong `src/arcade_agent/algorithms/architecture.py` tra cứu component của một entity bằng cách duyệt mọi component và kiểm tra `fqn in comp.entities` — trong đó `entities` là **list** → quét tuyến tính.

```python
# HIỆN TẠI (main @ 20d3728)
def component_of(self, fqn: str) -> str | None:
    for comp in self.components:
        if fqn in comp.entities:      # list membership = O(n) quét
            return comp.name
    return None
```

`component_dependencies()` gọi nó **2 lần cho mỗi edge** → tổng **O(E·n)**.

**Blast radius (đã grep toàn repo):** `component_dependencies` được gọi từ 8 nơi — `cycles.py`, `concern.py` (×2), `coupling.py` (×2), cả 3 exporter (`dot`, `mermaid`, `json`), và `query.py` (×4 — mỗi câu query của AI agent trả phí lại từ đầu). `component_of` còn nằm **trong vòng lặp edge** tại `query.py:72-73` và `explain_component.py:85-89`.

Chi tiết đáng chú ý: `coupling.py:161` đã có sẵn `_build_membership()` xây đúng dict index cần thiết — pattern fix **tồn tại sẵn trong codebase** nhưng chỉ được áp cục bộ, chưa đưa lên mức model.

## 2. Bản vá (toàn văn — cũng chính là nội dung file `.patch`)

```diff
--- a/src/arcade_agent/algorithms/architecture.py
+++ b/src/arcade_agent/algorithms/architecture.py
@@ -23,21 +23,32 @@ class Architecture:
     algorithm: str = ""  # pkg, wca, acdc, llm
     metadata: dict = field(default_factory=dict)
 
+    def membership(self) -> dict[str, str]:
+        """Build an entity-FQN → component-name index.
+
+        O(n) to build, O(1) per lookup. Computed fresh on each call so it can
+        never go stale if components are mutated; callers doing many lookups
+        should call this once and reuse the dict.
+        """
+        return {
+            fqn: comp.name
+            for comp in self.components
+            for fqn in comp.entities
+        }
+
     def component_of(self, fqn: str) -> str | None:
         """Find which component an entity belongs to."""
-        for comp in self.components:
-            if fqn in comp.entities:
-                return comp.name
-        return None
+        return self.membership().get(fqn)
 
     def component_dependencies(
         self, dep_graph: DependencyGraph
     ) -> list[tuple[str, str]]:
         """Compute component-level dependencies from entity-level edges."""
+        membership = self.membership()
         comp_edges: set[tuple[str, str]] = set()
         for edge in dep_graph.edges:
-            src_comp = self.component_of(edge.source)
-            tgt_comp = self.component_of(edge.target)
+            src_comp = membership.get(edge.source)
+            tgt_comp = membership.get(edge.target)
             if src_comp and tgt_comp and src_comp != tgt_comp:
                 comp_edges.add((src_comp, tgt_comp))
         return sorted(comp_edges)
```

**Quyết định thiết kế**: dict được xây tươi mỗi lần gọi thay vì cache trên instance — `Architecture` là mutable dataclass, cache instance có rủi ro stale nếu `components` bị sửa sau lần dùng đầu. Xây tươi = an toàn hành vi 100%; caller cần nhiều lookup thì tự giữ dict (gọi `membership()` một lần). Cache-có-invalidation là follow-up nếu profiling chứng minh cần.

## 3. Proof A — Dogfood: arcade-agent phân tích chính nó

Parse `src/arcade_agent` bằng chính parser Python của dự án, recover bằng thuật toán `pkg`:

```
graph: 291 entities, 155 edges → 6 components

component_dependencies() — best of 20 runs:
  current (list scan) : 0.410 ms
  indexed  (dict)     : 0.030 ms
  speedup             : 13.5×
  output identical    : True
```

## 4. Proof B — Scaling tổng hợp (chứng minh asymptotic)

Graph tổng hợp, edges = 4n, seed cố định (`random.Random(42)` — tái tạo được):

| n entities | components | current (ms) | indexed (ms) | speedup | identical |
|-----------:|-----------:|-------------:|-------------:|--------:|:---------:|
| 500 | 12 | 10.7 | 0.44 | 24× | True |
| 2,000 | 25 | 142.1 | 1.80 | 79× | True |
| 5,000 | 40 | 901.6 | 4.74 | 190× | True |
| 10,000 | 60 | 3,652.0 | 12.32 | **296×** | True |

Speedup **tăng theo n** (24× → 296×) — đây là chữ ký của việc hạ bậc phức tạp O(E·n) → O(E+n), không phải tối ưu constant-factor.

## 5. Proof C — Tương đương ngữ nghĩa end-to-end (proof quan trọng nhất)

Chạy A/B hai implementation trên **cùng một source tree, cùng graph** (implementation cũ được monkeypatch trở lại để so):

```
component_dependencies identical : True   (10 component deps)
detect_smells identical          : True   (4 smells: type, severity, affected — khớp từng cái)
compute_metrics identical        : True
  RCI=0.6774  TurboMQ=0.5355  BasicMQ=0.5355
  IntraConnectivity=0.008  InterConnectivity=0.0028  TwoWayPairRatio=0.0
```

⚠️ **Lưu ý phương pháp luận**: output KHÔNG được so với `.arcade/baseline.json` đã commit trong repo — đã thử và **không khớp**, vì baseline đó sinh từ commit cũ hơn source hiện tại. Phép so hợp lệ duy nhất là A/B cùng-commit như trên. (Nếu đưa proof vào PR, khai rõ điểm này — tránh bị reviewer bắt bẻ.)

## 6. Proof D — Test suite, lint, type check của chính dự án

```
pytest (loại test_mcp_e2e cần claude CLI):
  TRƯỚC patch : 165 passed, 3 skipped in 1.87s
  SAU   patch : 165 passed, 3 skipped in 0.85s    ← xanh nguyên vẹn

ruff check src/arcade_agent/algorithms/architecture.py : All checks passed
mypy : 1 error duy nhất tại dòng 24 `metadata: dict` — PRE-EXISTING của upstream,
       không do patch (method membership() được type đầy đủ dict[str, str])
```

## 7. Tái tạo toàn bộ trên máy local (repo này)

```bash
cd /Users/tuannguyen/Projects/tuannx/arcade-agent

# 0. (khuyến nghị) làm trên branch riêng
git checkout -b perf/membership-index

# 1. Môi trường
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# 2. Baseline test TRƯỚC patch
pytest --ignore=tests/test_mcp_e2e.py        # kỳ vọng: 165 passed, 3 skipped

# 3. Apply patch
git apply reports/perf-h1/h1-membership-index.patch

# 4. Kiểm chứng SAU patch
pytest --ignore=tests/test_mcp_e2e.py        # phải giữ nguyên 165 passed
ruff check src/

# 5. Tái tạo số liệu benchmark (sửa đường dẫn trong script nếu cần)
python reports/perf-h1/bench_h1.py
```

Lưu ý: `bench_h1.py` có 1 đường dẫn tuyệt đối `/home/claude/arcade-agent/src/arcade_agent` ở PART 1 (môi trường sandbox gốc) — đổi thành `src/arcade_agent` khi chạy từ repo root.

## 8. Bước tiếp theo

1. Chạy §7 để tự xác nhận trên máy bạn (proof trên máy owner > proof trên sandbox).
2. Mở issue theo draft trong playbook (`arcade-agent-issue-pr-playbook.md`) — title: `perf: Architecture.component_of does a linear list scan — component_dependencies is O(E·n)`.
3. Push branch + mở PR link issue, dán Proof A–D vào phần Test plan.
4. Follow-up sau khi merge: consolidate `_build_membership` trong `coupling.py` (PR riêng), rồi tiến tới H2 (ARC/LIMBO pair-cache — chi tiết trong `arcade-agent-phan-tich-do-phuc-tap.md`).
