package com.culturalmuseum.ai.controller;

import com.culturalmuseum.ai.service.GeminiService;
import com.culturalmuseum.ai.service.RagDataLoaderService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@RequestMapping("/api/chat")
@Tag(name = "Chatbot AI & RAG", description = "Endpoints cho Trợ lý ảo Bảo tàng tích hợp RAG tra cứu tri thức hiện vật")
public class ChatbotController {

    private final GeminiService geminiService;
    private final RagDataLoaderService ragDataLoaderService;

    public ChatbotController(GeminiService geminiService, RagDataLoaderService ragDataLoaderService) {
        this.geminiService = geminiService;
        this.ragDataLoaderService = ragDataLoaderService;
    }

    // 1. API CHAT VỚI BOT (Hỗ trợ RAG tra cứu hiện vật bảo tàng)
    @GetMapping
    @Operation(
            summary = "Chat với Hướng dẫn viên ảo (RAG)",
            description = "Gửi câu hỏi của du khách để nhận câu trả lời tra cứu từ kho tri thức hiện vật bảo tàng."
    )
    public ResponseEntity<Map<String, String>> chat(
            @Parameter(description = "Câu hỏi của du khách", example = "Trống đồng Ngọc Lũ thuộc niên đại nào?")
            @RequestParam String message) {

        String answer = geminiService.chatWithGemini(message);

        return ResponseEntity.ok(Map.of(
                "question", message,
                "answer", answer
        ));
    }

    // 2. API ĐỒNG BỘ DỮ LIỆU HIỆN VẬT VÀO VECTOR STORE (Dành cho Admin/Hệ thống)
    @PostMapping("/sync-knowledge")
    @Operation(summary = "Đồng bộ hiện vật vào Não AI", description = "Quét lại database và cập nhật Vector Database cho Chatbot")
    public ResponseEntity<String> syncKnowledge() {
        ragDataLoaderService.loadArtifactsToVectorStore();
        return ResponseEntity.ok("Đã đồng bộ toàn bộ hiện vật bảo tàng vào Vector Store thành công!");
    }
}
