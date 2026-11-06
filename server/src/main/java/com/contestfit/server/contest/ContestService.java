package com.contestfit.server.contest;

import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

import java.util.List;

@Service
@Transactional(readOnly = true)
public class ContestService {
    private final ContestRepository contestRepository;

    public ContestService(ContestRepository contestRepository) {
        this.contestRepository = contestRepository;
    }

    public List<ContestResponse> findAll() {
        return contestRepository.findAll().stream().map(ContestResponse::from).toList();
    }

    public ContestResponse findById(Long id) {
        return ContestResponse.from(contestRepository.findById(id)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "공모전을 찾을 수 없습니다.")));
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
