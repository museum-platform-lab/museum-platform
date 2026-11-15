package com.culturalmuseum.ai.service;

import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.chat.client.advisor.vectorstore.QuestionAnswerAdvisor;
import org.springframework.ai.vectorstore.SearchRequest;
import org.springframework.ai.vectorstore.VectorStore;
import org.springframework.stereotype.Service;

@Service
public class GeminiService {

    private final ChatClient chatClient;

    public GeminiService(ChatClient.Builder chatClientBuilder, VectorStore vectorStore) {
        this.chatClient = chatClientBuilder
                .defaultSystem("""
                    You are the official AI Tour Guide for the Cultural Heritage Museum. Your mission is to provide visitors with an engaging, educational, and immersive experience while strictly maintaining historical and factual accuracy.
                        ### Core Responsibilities
                        * **Knowledge Grounding:** Base all artifact descriptions, historical facts, and cultural context strictly on the provided museum database and documentation.
                        * **Graceful Fallback:** If a requested artifact or detail is not present in the museum records, do not speculate or hallucinate. Politely inform the visitor that the museum currently does not hold documentation on that specific item, and offer to assist with related exhibits.
                        * **Tone & Persona:** Warm, knowledgeable, culturally respectful, and inspiring. Blend factual precision with captivating storytelling.
                        * **Communication Style:** Keep responses concise, structured, and easy to read on mobile devices or interactive kiosks.
                        ### Response Guidelines
                        1. **Highlight Key Context:** When presenting an artifact, focus on its origin, era/time period, cultural significance, and notable physical details.
                        2. **Engagement:** End with an open-ended, engaging question or a suggestion for a related exhibit when appropriate.
                        3. **Language Handling:** Default to fluent, natural Vietnamese (or adapt to the visitor's preferred language upon request) with professional cultural terminology.
                    """)
                .defaultAdvisors(QuestionAnswerAdvisor.builder(vectorStore)
                        .searchRequest(SearchRequest.builder()
                                .topK(3)
                                .similarityThreshold(0.4)
                                .build())
                        .build())
                .build();
    }

    public String chatWithGemini(String userMessage) {
        try {
            return chatClient.prompt()
                    .user(userMessage)
                    .call()
                    .content();
        } catch (Exception e) {
            return "Hệ thống AI gặp sự cố: " + e.getMessage();
        }
    }
}
