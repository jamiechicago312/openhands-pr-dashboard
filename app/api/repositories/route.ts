import { NextRequest, NextResponse } from 'next/server'
import { Octokit } from '@octokit/rest'
import { config } from '@/lib/config'

const octokit = new Octokit({
  auth: process.env.GITHUB_TOKEN,
})

const excludedRepos = new Set(config.repos.exclude.map(repo => repo.trim().toLowerCase()))

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url)
    const specificOrg = searchParams.get('org')

    // Determine which organizations to fetch from
    const orgsToFetch = specificOrg ? [specificOrg] : config.orgs

    console.log('Fetching repositories from organizations:', orgsToFetch)

    // Fetch repositories from all target organizations
    const allRepositories = []
    
    for (const org of orgsToFetch) {
      try {
        console.log(`Fetching repositories for org: ${org}`)
        
        // Paginate through all repositories
        let page = 1
        let hasMore = true
        let orgRepoCount = 0
        
        while (hasMore) {
          const { data: repositories } = await octokit.rest.repos.listForOrg({
            org,
            type: 'public',
            sort: 'updated',
            per_page: 100,
            page,
          })

          if (repositories.length === 0) {
            hasMore = false
          } else {
            allRepositories.push(...repositories)
            orgRepoCount += repositories.length
            page++
            
            // Stop if we got fewer than 100 repos (last page)
            if (repositories.length < 100) {
              hasMore = false
            }
          }
        }

        console.log(`Found ${orgRepoCount} repositories for ${org}`)
      } catch (orgError) {
        console.error(`Error fetching repositories for org ${org}:`, orgError)
        // Continue with other orgs even if one fails
      }
    }

    // Filter and format repositories
    const formattedRepos = Array.from(
      new Map(
        allRepositories
          .filter(repo => !repo.archived && !repo.disabled)
          .filter(repo => !excludedRepos.has(repo.full_name.toLowerCase()))
          .map(repo => [repo.full_name.toLowerCase(), {
            id: repo.id,
            name: repo.name,
            full_name: repo.full_name,
            description: repo.description,
            stargazers_count: repo.stargazers_count,
            language: repo.language,
            updated_at: repo.updated_at,
            html_url: repo.html_url,
          }])
      ).values()
    ).sort((a, b) => (b.stargazers_count || 0) - (a.stargazers_count || 0)) // Sort by stars

    console.log(`Total formatted repositories: ${formattedRepos.length}`)

    return NextResponse.json({
      repositories: formattedRepos,
      total: formattedRepos.length,
      organizations: orgsToFetch,
    })
  } catch (error) {
    console.error('Error fetching repositories:', error)
    
    // Return fallback data if API fails
    const fallbackRepos = [
      {
        id: 1,
        name: 'OpenHands',
        full_name: 'OpenHands/OpenHands',
        description: 'OpenHands: Code Less, Make More',
        stargazers_count: 35000,
        language: 'Python',
        updated_at: new Date().toISOString(),
        html_url: 'https://github.com/OpenHands/OpenHands',
      },
      {
        id: 2,
        name: 'community-pr-dashboard',
        full_name: 'OpenHands/community-pr-dashboard',
        description: 'Dashboard for tracking community pull requests and review accountability',
        stargazers_count: 0,
        language: 'TypeScript',
        updated_at: new Date().toISOString(),
        html_url: 'https://github.com/OpenHands/community-pr-dashboard',
      },
      {
        id: 3,
        name: 'docs',
        full_name: 'OpenHands/docs',
        description: 'OpenHands documentation site',
        stargazers_count: 0,
        language: 'TypeScript',
        updated_at: new Date().toISOString(),
        html_url: 'https://github.com/OpenHands/docs',
      },
    ]

    return NextResponse.json({
      repositories: fallbackRepos.filter(repo => !excludedRepos.has(repo.full_name.toLowerCase())),
      total: fallbackRepos.filter(repo => !excludedRepos.has(repo.full_name.toLowerCase())).length,
      organizations: config.orgs,
      error: 'Using fallback data due to API error',
    })
  }
}

export const dynamic = 'force-dynamic'