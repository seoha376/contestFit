package com.contestfit.server.contest;

import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.util.List;

@Service
@Transactional(readOnly = true)
public class ContestService {
    private final ContestRepository contestRepository;
    private final ObjectMapper objectMapper;

    public ContestService(ContestRepository contestRepository, ObjectMapper objectMapper) {
        this.contestRepository = contestRepository;
        this.objectMapper = objectMapper;
    }

    public List<ContestResponse> findAll() {
        return contestRepository.findAll().stream().map(ContestResponse::from).toList();
    }

    public ContestResponse findById(Long id) {
        return ContestResponse.from(contestRepository.findById(id)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "공모전을 찾을 수 없습니다.")));
    }

    public List<JsonNode> findSeedFeed() {
        return contestRepository.findAllBySeedPayloadIsNotNullOrderByIdAsc().stream()
                .map(Contest::getSeedPayload)
                .map(this::readPayload)
                .toList();
    }

    private JsonNode readPayload(String payload) {
        try {
            return objectMapper.readTree(payload);
        } catch (JsonProcessingException exception) {
            throw new IllegalStateException("저장된 공모전 피드 형식이 올바르지 않습니다.", exception);
        }
    }

    @Transactional
    public ContestResponse create(CreateContestRequest request) {
        Contest contest = new Contest(request.title(), request.category(), request.deadline(), request.sourceUrl(), request.validationStatus());
        if (request.eligibilityRules() != null) {
            request.eligibilityRules().forEach(rule -> contest.addEligibilityRule(
                    new EligibilityRule(rule.field(), rule.operator(), rule.value(), rule.evidenceQuote())
            ));
        }
        return ContestResponse.from(contestRepository.save(contest));
    }
}
