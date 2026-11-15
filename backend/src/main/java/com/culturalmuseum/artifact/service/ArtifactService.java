package com.culturalmuseum.artifact.service;

import com.culturalmuseum.artifact.dto.request.ArtifactCreationRequest;
import com.culturalmuseum.artifact.dto.request.ArtifactUpdateRequest;
import com.culturalmuseum.artifact.dto.response.ArtifactResponse;
import com.culturalmuseum.artifact.entity.Artifact;
import com.culturalmuseum.artifact.repository.ArtifactRepository;
import com.culturalmuseum.auth.entity.User;
import com.culturalmuseum.auth.repository.UserRepository;
import org.springframework.stereotype.Service;

import java.time.OffsetDateTime;
import java.util.List;

@Service
public class ArtifactService {

    private static final int STATUS_ACTIVE = 1;
    private static final int STATUS_DELETED = 0;

    private static final String PENDING = "PENDING";
    private static final String APPROVED = "APPROVED";
    private static final String REJECTED = "REJECTED";

    private final ArtifactRepository artifactRepository;
    private final UserRepository userRepository;

    public ArtifactService(ArtifactRepository artifactRepository, UserRepository userRepository) {
        this.artifactRepository = artifactRepository;
        this.userRepository = userRepository;
    }

    // Helper: Tìm entity Artifact active dùng nội bộ Service
    public Artifact findActiveArtifactById(Long id) {
        return artifactRepository.findByIdAndStatus(id, STATUS_ACTIVE)
                .orElseThrow(() -> new RuntimeException("Artifact not found or deactivated with id: " + id));
    }

    // ==========================================
    // 1. PUBLIC & USER APIs
    // ==========================================

    // READ ALL ARTIFACTS (Active & APPROVED only - For Public View)
    public List<ArtifactResponse> getPublicArtifacts() {
        return artifactRepository.findAllByApprovalStatusAndStatus(APPROVED, STATUS_ACTIVE)
                .stream()
                .map(ArtifactResponse::fromEntity)
                .toList();
    }

    // READ ARTIFACT BY ID (Active & APPROVED only - For Public View)
    public ArtifactResponse getPublicArtifactById(Long id) {
        Artifact artifact = findActiveArtifactById(id);
        if (!APPROVED.equals(artifact.getApprovalStatus())) {
            throw new RuntimeException("Artifact not found or not yet approved");
        }
        return ArtifactResponse.fromEntity(artifact);
    }

    // CONTRIBUTE ARTIFACT (For Logged-in Users)
    public ArtifactResponse createContributedArtifact(ArtifactCreationRequest request, Long contributorId) {
        Artifact artifact = new Artifact();

        artifact.setName(request.getName());
        artifact.setShortDescription(request.getShortDescription());
        artifact.setDescription(request.getDescription());
        artifact.setCategories(request.getCategories());
        artifact.setMainImageUrl(request.getMainImageUrl());
        artifact.setSupportingImages(request.getSupportingImages());
        artifact.setAuthor(request.getAuthor());
        artifact.setArtifactEra(request.getArtifactEra());
        artifact.setPublicDate(request.getPublicDate());
        artifact.setLocation(request.getLocation());

        // Thiết lập trạng thái
        artifact.setStatus(STATUS_ACTIVE);
        artifact.setApprovalStatus(PENDING); // Bắt buộc là PENDING để chờ duyệt

        // Gắn thông tin người dùng dựa vào Context
        User contributor = userRepository.findById(contributorId)
                .orElseThrow(() -> new RuntimeException("Contributor not found"));
        
        artifact.setContributor(contributor);
        artifact.setContributorName(contributor.getFirstName() + " " + contributor.getLastName());

        Artifact savedArtifact = artifactRepository.save(artifact);
        return ArtifactResponse.fromEntity(savedArtifact);
    }


    // ==========================================
    // 2. ADMIN APIs
    // ==========================================

    // Lấy danh sách hiện vật đang chờ duyệt
    public List<ArtifactResponse> getPendingArtifacts() {
        return artifactRepository.findAllByApprovalStatusAndStatus(PENDING, STATUS_ACTIVE)
                .stream()
                .map(ArtifactResponse::fromEntity)
                .toList();
    }

    // Phê duyệt hiện vật
    public ArtifactResponse approveArtifact(Long id) {
        Artifact artifact = findActiveArtifactById(id);
        
        if (APPROVED.equals(artifact.getApprovalStatus())) {
            throw new RuntimeException("Artifact is already approved");
        }
        
        artifact.setApprovalStatus(APPROVED);
        artifact.setApprovedAt(OffsetDateTime.now());
        
        Artifact savedArtifact = artifactRepository.save(artifact);
        return ArtifactResponse.fromEntity(savedArtifact);
    }

    // Từ chối hiện vật
    public ArtifactResponse rejectArtifact(Long id, String adminNote) {
        Artifact artifact = findActiveArtifactById(id);
        
        artifact.setApprovalStatus(REJECTED);
        artifact.setAdminNote(adminNote);
        
        Artifact savedArtifact = artifactRepository.save(artifact);
        return ArtifactResponse.fromEntity(savedArtifact);
    }
    
    // (Giữ lại hàm Create cho Admin import nội bộ, nếu cần)
    public ArtifactResponse createArtifactByAdmin(ArtifactCreationRequest request) {
        Artifact artifact = new Artifact();
        // ... set properties ... 
        // Lấy nhanh tự tương tự như cũ, gắn trực tiếp APPROVED
        artifact.setName(request.getName());
        artifact.setShortDescription(request.getShortDescription());
        artifact.setDescription(request.getDescription());
        artifact.setCategories(request.getCategories());
        artifact.setMainImageUrl(request.getMainImageUrl());
        artifact.setSupportingImages(request.getSupportingImages());
        artifact.setAuthor(request.getAuthor());
        artifact.setContributorName(request.getContributorName());
        artifact.setArtifactEra(request.getArtifactEra());
        artifact.setPublicDate(request.getPublicDate());
        artifact.setLocation(request.getLocation());
        artifact.setStatus(STATUS_ACTIVE);
        artifact.setApprovalStatus(APPROVED); // Mặc định do admin thêm là APPROVED
        artifact.setApprovedAt(OffsetDateTime.now());

        if (request.getContributorId() != null) {
            User contributor = userRepository.findById(request.getContributorId()).orElse(null);
            artifact.setContributor(contributor);
        }

        Artifact savedArtifact = artifactRepository.save(artifact);
        return ArtifactResponse.fromEntity(savedArtifact);
    }

    // UPDATE ARTIFACT (Admin)
    public ArtifactResponse updateArtifact(Long id, ArtifactUpdateRequest request) {
        Artifact artifact = findActiveArtifactById(id);

        if (request.getName() != null) artifact.setName(request.getName());
        if (request.getShortDescription() != null) artifact.setShortDescription(request.getShortDescription());
        if (request.getDescription() != null) artifact.setDescription(request.getDescription());
        if (request.getCategories() != null) artifact.setCategories(request.getCategories());
        if (request.getMainImageUrl() != null) artifact.setMainImageUrl(request.getMainImageUrl());
        if (request.getSupportingImages() != null) artifact.setSupportingImages(request.getSupportingImages());
        if (request.getAuthor() != null) artifact.setAuthor(request.getAuthor());
        if (request.getContributorName() != null) artifact.setContributorName(request.getContributorName());
        if (request.getArtifactEra() != null) artifact.setArtifactEra(request.getArtifactEra());
        if (request.getPublicDate() != null) artifact.setPublicDate(request.getPublicDate());
        if (request.getLocation() != null) artifact.setLocation(request.getLocation());
        if (request.getApprovalStatus() != null) artifact.setApprovalStatus(request.getApprovalStatus());
        if (request.getAdminNote() != null) artifact.setAdminNote(request.getAdminNote());

        Artifact updatedArtifact = artifactRepository.save(artifact);
        return ArtifactResponse.fromEntity(updatedArtifact);
    }

    // SOFT DELETE ARTIFACT (Admin)
    public void deleteArtifact(Long id) {
        Artifact artifact = findActiveArtifactById(id);
        artifact.setStatus(STATUS_DELETED);
        artifactRepository.save(artifact);
    }
}
