//package com.culturalmuseum.config;
//
//import com.culturalmuseum.artifact.entity.Artifact;
//import com.culturalmuseum.artifact.repository.ArtifactRepository;
//import org.apache.commons.csv.CSVFormat;
//import org.apache.commons.csv.CSVParser;
//import org.apache.commons.csv.CSVRecord;
//import org.springframework.boot.CommandLineRunner;
//import org.springframework.core.io.ClassPathResource;
//import org.springframework.stereotype.Component;
//
//import java.io.BufferedReader;
//import java.io.InputStreamReader;
//import java.nio.charset.StandardCharsets;
//
//@Component
//public class CsvDataSeeder implements CommandLineRunner {
//
//    private final ArtifactRepository artifactRepository;
//
//    public CsvDataSeeder(ArtifactRepository artifactRepository) {
//        this.artifactRepository = artifactRepository;
//    }
//
//    @Override
//    public void run(String... args) throws Exception {
//        // Chỉ chạy add dữ liệu nếu bảng artifacts đang trống (Tránh bị add trùng lặp khi restart server nhiều lần)
//        if (artifactRepository.count() == 0) {
//            System.out.println("⏳ Đang bắt đầu import dữ liệu từ file CSV vào Database...");
//
//            ClassPathResource resource = new ClassPathResource("artifacts.csv");
//
//            // Cấu hình báo cho thư viện biết là dòng đầu tiên là Header (tên cột)
//            CSVFormat csvFormat = CSVFormat.Builder.create()
//                    .setHeader()
//                    .setSkipHeaderRecord(true)
//                    .setIgnoreHeaderCase(true)
//                    .setTrim(true)
//                    .build();
//
//            // Sử dụng try-with-resources để tự động giải phóng tài nguyên và đóng file sau khi đọc xong
//            try (BufferedReader reader = new BufferedReader(
//                    new InputStreamReader(resource.getInputStream(), StandardCharsets.UTF_8));
//                 CSVParser csvParser = new CSVParser(reader, csvFormat)) {
//
//                int count = 0;
//
//                for (CSVRecord record : csvParser) {
//                    Artifact artifact = new Artifact();
//
//                    // Các Default Value bắt buộc của hệ thống
//                    artifact.setApprovalStatus("APPROVED"); // Coi như CSV import vào đã được duyệt
//                    artifact.setStatus(1); // 1 = Active
//
//                    artifact.setName(getRecordValue(record, "Name"));
//                    artifact.setShortDescription(getRecordValue(record, "Short Description"));
//                    artifact.setDescription(getRecordValue(record, "Description"));
//                    artifact.setCategories(getRecordValue(record, "Categories"));
//                    artifact.setMainImageUrl(getRecordValue(record, "Main Image URL"));
//                    artifact.setSupportingImages(getRecordValue(record, "Supporting Images"));
//                    artifact.setAuthor(getRecordValue(record, "Author"));
//                    artifact.setContributorName(getRecordValue(record, "Contributor"));
//                    artifact.setArtifactEra(getRecordValue(record, "Artifact Era"));
//                    artifact.setPublicDate(getRecordValue(record, "Public Date"));
//                    artifact.setLocation(getRecordValue(record, "Location"));
//
//                    artifactRepository.save(artifact);
//                    count++;
//                }
//
//                System.out.println("✅ Import thành công " + count + " hiện vật từ CSV vào Database!");
//
//            } catch (Exception e) {
//                System.err.println("❌ Lỗi khi đọc file CSV: " + e.getMessage());
//            }
//        } else {
//            System.out.println("👍 Database đã có dữ liệu, tự động bỏ qua bước import CSV.");
//        }
//    }
//
//    // Hàm tiện ích: Lấy giá trị của cột trong CSV, nếu cột không tồn tại thì trả về null
//    private String getRecordValue(CSVRecord record, String headerColumnName) {
//        if (record.isMapped(headerColumnName)) {
//            return record.get(headerColumnName);
//        }
//        return null; // File CSV không có cột này
//    }
//}
