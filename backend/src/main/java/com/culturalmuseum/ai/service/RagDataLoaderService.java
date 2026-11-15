package com.culturalmuseum.ai.service;

import com.culturalmuseum.artifact.entity.Artifact;
import com.culturalmuseum.artifact.repository.ArtifactRepository;
import org.springframework.ai.document.Document;
import org.springframework.ai.vectorstore.VectorStore;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.nio.charset.StandardCharsets;
import java.util.*;

@Service
public class RagDataLoaderService {

    private final ArtifactRepository artifactRepository;
    private final VectorStore vectorStore;
    private final JdbcTemplate jdbcTemplate;

    public RagDataLoaderService(ArtifactRepository artifactRepository,
                                VectorStore vectorStore,
                                JdbcTemplate jdbcTemplate) {
        this.artifactRepository = artifactRepository;
        this.vectorStore = vectorStore;
        this.jdbcTemplate = jdbcTemplate;
    }

    /**
     * Đồng bộ dữ liệu tăng tiến (Incremental Sync):
     * Chỉ nạp các hiện vật chưa từng được lưu vào Vector Store, giữ nguyên dữ liệu đã có.
     */
    public void loadArtifactsToVectorStore() {
        List<Artifact> approvedArtifacts = artifactRepository.findAllByApprovalStatusAndStatus("APPROVED", 1);

        if (approvedArtifacts.isEmpty()) {
            System.out.println(">>> Không có hiện vật nào ở trạng thái APPROVED trong Database.");
            return;
        }

        // 1. Lấy danh sách ID các hiện vật ĐÃ CÓ trong vector_store để tránh nạp lại
        Set<Long> existingIds = new HashSet<>();
        try {
            //noinspection SqlResolve
            List<Long> ids = jdbcTemplate.queryForList(
                    "SELECT (metadata->>'artifactId')::bigint FROM vector_store WHERE metadata->>'artifactId' IS NOT NULL",
                    Long.class
            );
            existingIds.addAll(ids);
        } catch (Exception e) {
            System.out.println(">>> [Lưu ý] Chưa thể lấy danh sách ID từ vector_store (bảng có thể chưa khởi tạo): " + e.getMessage());
        }

        // 2. Lọc ra danh sách hiện vật CHƯA ĐỒNG BỘ (Incremental)
        List<Artifact> unindexedArtifacts = approvedArtifacts.stream()
                .filter(artifact -> !existingIds.contains(artifact.getId()))
                .toList();

        if (unindexedArtifacts.isEmpty()) {
            System.out.printf(">>> Toàn bộ %d hiện vật đã có trong Vector Store. Không cần nạp thêm!%n", approvedArtifacts.size());
            return;
        }

        System.out.printf(">>> Phát hiện %d hiện vật chưa đồng bộ (đã có %d hiện vật). Bắt đầu nạp tiếp...%n",
                unindexedArtifacts.size(), existingIds.size());

        // 3. Chuyển đổi các hiện vật chưa nạp sang Document
        List<Document> documents = unindexedArtifacts.stream().map(artifact -> {
            String name = defaultStr(artifact.getName());
            String era = defaultStr(artifact.getArtifactEra());
            String categories = defaultStr(artifact.getCategories());
            String location = defaultStr(artifact.getLocation());
            String shortDesc = defaultStr(artifact.getShortDescription());
            String desc = defaultStr(artifact.getDescription());

            // Nội dung ngữ nghĩa chuẩn hóa để AI tra cứu chính xác
            String content = String.format(
                    "Hiện vật: %s. Niên đại: %s. Thể loại: %s. Địa điểm: %s. Mô tả ngắn: %s. Mô tả chi tiết: %s",
                    name, era, categories, location, shortDesc, desc
            );

            Map<String, Object> metadata = new HashMap<>();
            metadata.put("artifactId", artifact.getId() != null ? artifact.getId() : 0L);
            metadata.put("artifactName", name);
            metadata.put("era", era);

            // Sinh UUID chuẩn v3 định danh cho hiện vật
            String docId = UUID.nameUUIDFromBytes(("artifact_" + artifact.getId()).getBytes(StandardCharsets.UTF_8)).toString();
            return new Document(docId, content, metadata);
        }).toList();

        // 4. Phân đoạn nạp từng đợt (Batching) để chống lỗi HTTP 429
        int batchSize = 40;
        int totalBatches = (int) Math.ceil((double) documents.size() / batchSize);

        for (int i = 0; i < documents.size(); i += batchSize) {
            List<Document> batch = documents.subList(i, Math.min(i + batchSize, documents.size()));
            vectorStore.add(batch);

            int currentBatch = (i / batchSize) + 1;
            System.out.printf(">>> Đã nạp thành công lô [%d/%d] (%d hiện vật)...%n", currentBatch, totalBatches, batch.size());

            // Nghỉ giữa các lô để bảo vệ Quota (trừ lô cuối cùng)
            if (i + batchSize < documents.size()) {
                System.out.println(">>> Đang tạm nghỉ 30 giây để bảo vệ Quota Google AI Studio (tránh lỗi 429)...");
                try {
                    Thread.sleep(30000);
                } catch (InterruptedException ignored) {
                    Thread.currentThread().interrupt();
                }
            }
        }

        System.out.println(">>> Đã hoàn tất đồng bộ các hiện vật mới vào Vector Store (RAG)!");
    }

    private String defaultStr(String str) {
        return (str == null || str.isBlank()) ? "Chưa có thông tin" : str.trim();
    }
}
