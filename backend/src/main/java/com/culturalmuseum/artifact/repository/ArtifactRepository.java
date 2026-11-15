package com.culturalmuseum.artifact.repository;

import com.culturalmuseum.artifact.entity.Artifact;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

@Repository
public interface ArtifactRepository extends JpaRepository<Artifact, Long> {

    // Tìm hiện vật còn active theo ID
    Optional<Artifact> findByIdAndStatus(Long id, Integer status);

    // Lấy toàn bộ hiện vật theo trạng thái xóa mềm
    List<Artifact> findAllByStatus(Integer status);

    // Lấy hiện vật theo trạng thái duyệt (PENDING, APPROVED, REJECTED) và còn active
    List<Artifact> findAllByApprovalStatusAndStatus(String approvalStatus, Integer status);

    // Tìm kiếm theo tên (không phân biệt hoa thường) và còn active
    List<Artifact> findByNameContainingIgnoreCaseAndStatus(String name, Integer status);

    // Tìm kiếm theo niên đại và còn active
    List<Artifact> findByArtifactEraAndStatus(String era, Integer status);

    // Lấy tất cả hiện vật do một User đóng góp
    List<Artifact> findAllByContributor_IdAndStatus(Long userId, Integer status);
}
